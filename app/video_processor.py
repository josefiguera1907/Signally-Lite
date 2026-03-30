import os
import subprocess
import logging
import time
from queue import Queue, Empty
from threading import Thread, RLock
from datetime import datetime

# Configuración de logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ── Verificar dependencias del sistema al importar ────────────────────────────
def _check_system_deps():
    """Comprueba que ffmpeg y ffprobe estén disponibles en el PATH."""
    missing = []
    for bin_name in ('ffmpeg', 'ffprobe'):
        result = subprocess.run(['which', bin_name],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0:
            missing.append(bin_name)
    if missing:
        logger.error(
            "=" * 60 + "\n"
            "DEPENDENCIAS FALTANTES: %s\n"
            "La transcodificación de video NO funcionará hasta instalarlas.\n"
            "Solución en Debian/Ubuntu/LXC:\n"
            "  apt update && apt install -y ffmpeg\n"
            "O ejecuta el script de instalación del proyecto:\n"
            "  bash install_deps.sh\n"
            + "=" * 60,
            ", ".join(missing)
        )
    else:
        logger.info("✓ ffmpeg y ffprobe detectados correctamente.")

_check_system_deps()


class VideoProcessor:
    _instance = None
    _lock = RLock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(VideoProcessor, cls).__new__(cls)
                cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if getattr(self, '_initialized', False):
            return
            
        self._initialized = True
        self.task_queue = Queue()
        self.active_tasks = {}
        self.completed_tasks = {}
        self.queued_tasks = {}
        self._stop_event = False
        self.workers = []
        self.worker_count = 0
        self.lock = RLock()
        
        # Configuración por defecto de transcodificación
        self.default_config = {
            'video_codec': 'libx264',
            'preset': 'medium',
            'crf': '20',  # Calidad aumentada (valor más bajo = más calidad)
            'audio_codec': 'aac',
            'audio_bitrate': '192k', # Calidad de audio aumentada
            'pix_fmt': 'yuv420p',
            'output_extension': '.mp4'
        }
    
    def start_workers(self, num_workers=None):
        """Inicia los workers para procesar tareas en segundo plano. 
        
        Args:
            num_workers: Número de workers a iniciar. Si es None, se calculará automáticamente.
        """
        with self.lock:
            if self.workers:
                logger.warning("Los workers ya están en ejecución")
                return
                
            if num_workers is None:
                # Calcular el número de workers: la mitad de los núcleos de CPU, pero al menos 1.
                # Esto evita sobrecargar el sistema, ya que cada worker (ffmpeg) puede usar múltiples hilos.
                cpu_cores = os.cpu_count() or 1
                num_workers = max(1, cpu_cores // 2)
            
            self._stop_event = False
            self.workers = []
            
            for _ in range(num_workers):
                self.worker_count += 1
                worker = Thread(
                    target=self._worker_loop,
                    daemon=True,
                    name=f'VideoWorker-{self.worker_count}'
                )
                worker.start()
                self.workers.append(worker)
            
            logger.info(f"Iniciados {num_workers} workers de transcodificación basados en {cpu_cores} núcleos de CPU.")
    
    def _worker_loop(self):
        """Bucle principal del worker que procesa tareas de la cola."""
        while not self._stop_event:
            try:
                try:
                    task = self.task_queue.get(timeout=1)
                except Empty:
                    continue
                    
                if task is None:
                    break
                    
                task_id, task_func, args, kwargs = task

                task_info = {}
                with self.lock:
                    if task_id in self.queued_tasks:
                        task_info = self.queued_tasks.pop(task_id)
                    task_info.update({
                        'start_time': datetime.now(),
                        'status': 'processing',
                        'progress': 0
                    })
                    self.active_tasks[task_id] = task_info
                
                try:
                    result = task_func(*args, **kwargs)

                    if result.get('success'):
                        with self.lock:
                            completed_task_info = self.active_tasks.pop(task_id, task_info)
                            completed_task_info.update({
                                'end_time': datetime.now(),
                                'status': 'completed',
                                'result': result,
                                'progress': 100
                            })
                            self.completed_tasks[task_id] = completed_task_info
                    else:
                        error_msg = result.get('error', 'Unknown error during task execution')
                        logger.error(f"Task {task_id} failed: {error_msg}")
                        with self.lock:
                            failed_task_info = self.active_tasks.pop(task_id, task_info)
                            failed_task_info.update({
                                'end_time': datetime.now(),
                                'status': 'failed',
                                'error': error_msg
                            })
                            self.completed_tasks[task_id] = failed_task_info

                except Exception as e:
                    error_msg = f"Unexpected exception while processing task {task_id}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    with self.lock:
                        failed_task_info = self.active_tasks.pop(task_id, task_info)
                        failed_task_info.update({
                            'end_time': datetime.now(),
                            'status': 'failed',
                            'error': error_msg
                        })
                        self.completed_tasks[task_id] = failed_task_info
                finally:
                    self.task_queue.task_done()
                    
            except Exception as e:
                if not self._stop_event:
                    logger.error(f"Unexpected error in worker loop: {str(e)}", exc_info=True)
                    time.sleep(1)
    
    def submit_task(self, task_func, *args, **kwargs):
        """Envía una tarea a la cola de procesamiento. 
        
        Args:
            task_func: Función a ejecutar
            *args, **kwargs: Argumentos para la función
            
        Returns:
            str: ID de la tarea
        """
        task_id = f"task_{len(self.active_tasks) + len(self.completed_tasks) + len(self.queued_tasks) + 1}"
        self.task_queue.put((task_id, task_func, args, kwargs))
        return task_id
    
    def get_task_status(self, task_id):
        """Obtiene el estado de una tarea. 
        
        Args:
            task_id: ID de la tarea
            
        Returns:
            dict: Estado de la tarea o None si no existe
        """
        with self.lock:
            if task_id in self.active_tasks:
                return {'status': 'processing', **self.active_tasks[task_id]}
            elif task_id in self.completed_tasks:
                return self.completed_tasks[task_id]
            elif task_id in self.queued_tasks:
                return {'status': 'queued', **self.queued_tasks[task_id]}
        return None
    
    def stop_workers(self):
        """Detiene todos los workers y limpia recursos."""
        with self.lock:
            if not self.workers:
                logger.info("No hay workers activos para detener")
                return
                
            logger.info("Deteniendo workers de transcodificación...")
            self._stop_event = True
            
            # Enviar señal de parada a todos los workers
            for _ in self.workers:
                self.task_queue.put(None)
            
            # Esperar a que los workers terminen
            for worker in self.workers:
                if worker.is_alive():
                    worker.join(timeout=5)
                    if worker.is_alive():
                        logger.warning(f"Worker {worker.name} no se detuvo correctamente")
            
            self.workers = []
            self.active_tasks.clear()
            logger.info("Todos los workers han sido detenidos")
    
    def get_active_task_count(self):
        """Obtiene el número de tareas activas."""
        with self.lock:
            return len(self.active_tasks)
    
    def get_queue_size(self):
        """Obtiene el número de tareas en cola."""
        return self.task_queue.qsize()
    
    def get_worker_count(self):
        """Obtiene el número de workers activos."""
        with self.lock:
            return len([w for w in self.workers if w.is_alive()])

    def cancel_task(self, task_id):
        """Cancela una tarea de transcodificación, ya sea activa o en cola."""
        with self.lock:
            # Caso 1: La tarea está activa, hay que detener el proceso y limpiar
            if task_id in self.active_tasks:
                task = self.active_tasks.pop(task_id)
                
                # Detener el proceso si se está ejecutando
                process = task.get('process')
                if process and process.poll() is None:
                    try:
                        process.kill()
                        logger.info(f"Proceso de transcodificación activo para la tarea {task_id} ha sido detenido.")
                    except Exception as e:
                        logger.error(f"Error al detener el proceso para la tarea {task_id}: {e}")
                
                # Limpiar el archivo temporal .tmp
                output_path = task.get('output_path')
                if output_path:
                    temp_output_path = output_path + ".tmp"
                    if os.path.exists(temp_output_path):
                        try:
                            os.remove(temp_output_path)
                            logger.info(f"Archivo temporal {temp_output_path} eliminado.")
                        except OSError as e:
                            logger.error(f"Error al eliminar el archivo temporal {temp_output_path}: {e}")

                task['status'] = 'cancelled'
                task['error'] = 'La tarea fue cancelada por el usuario.'
                self.completed_tasks[task_id] = task
                return True

            # Caso 2: La tarea está en la cola, hay que eliminarla
            if task_id in self.queued_tasks:
                self.queued_tasks.pop(task_id)
                new_queue_items = []
                while not self.task_queue.empty():
                    try:
                        item = self.task_queue.get_nowait()
                        if item[0] != task_id:
                            new_queue_items.append(item)
                    except Empty:
                        break
                for item in new_queue_items:
                    self.task_queue.put(item)
                
                logger.info(f"Tarea en cola {task_id} ha sido eliminada.")
                return True
        
        logger.warning(f"No se encontró la tarea {task_id} para cancelar.")
        return False
    
    def submit_transcode_task(self, input_path, output_path=None, config=None):
        """Envía una tarea de transcodificación a la cola. 
        
        Args:
            input_path: Ruta al archivo de entrada
            output_path: Ruta de salida (opcional, se genera automáticamente si es None)
            config: Configuración de transcodificación (opcional)
            
        Returns:
            tuple: (task_id, output_path) o (None, error_message) en caso de error
        """
        try:
            if not os.path.isfile(input_path):
                return None, f"El archivo de entrada no existe: {input_path}"
            
            if output_path is None:
                base_name = os.path.splitext(os.path.basename(input_path))[0]
                output_path = os.path.join(
                    os.path.dirname(os.path.dirname(input_path)),
                    'transcodificados',
                    f"{base_name}.mp4"
                )
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            task_id = f"task_{len(self.active_tasks) + len(self.completed_tasks) + len(self.queued_tasks) + 1}"

            task_kwargs = {
                'input_path': input_path,
                'output_path': output_path,
                'config': config,
                'task_id': task_id
            }

            self.task_queue.put((task_id, transcode_video, (), task_kwargs))

            with self.lock:
                self.queued_tasks[task_id] = {
                    'filename': os.path.basename(input_path),
                    'input_path': input_path,
                    'output_path': output_path,
                    'submit_time': datetime.now()
                }
            
            logger.info(f"Tarea de transcodificación enviada (ID: {task_id}): {input_path} -> {output_path}")
            return task_id, output_path
            
        except Exception as e:
            error_msg = f"Error al enviar tarea de transcodificación: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return None, error_msg

def transcode_video(input_path, output_path, config=None, task_id=None):
    """Transcodifica un video al formato optimo para transmision de forma atomica.

    Usa aceleracion GPU (VAAPI) si esta configurada en config_manager,
    con fallback automatico a CPU si la GPU no esta disponible.
    """
    processor = VideoProcessor()
    if config is None:
        config = processor.default_config

    temp_output_path = output_path + ".tmp"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if os.path.exists(temp_output_path):
        os.remove(temp_output_path)

    total_duration = get_video_duration(input_path)

    # Leer configuracion de aceleracion de hardware
    try:
        from .config_manager import config_manager
        video_cfg = config_manager.get_video_config()
        use_gpu   = video_cfg.get('hardware_accel') == 'gpu'
        gpu_device = video_cfg.get('gpu_device', '/dev/dri/renderD128')
    except Exception:
        use_gpu    = False
        gpu_device = '/dev/dri/renderD128'

    audio_params = ['-c:a', config['audio_codec'], '-b:a', config['audio_bitrate'], '-ac', '2', '-ar', '44100']

    def build_cpu_cmd():
        return [
            'ffmpeg', '-y', '-nostdin',
            '-i', input_path,
            '-c:v', config['video_codec'],
            '-preset', config['preset'],
            '-crf', str(config['crf']),
            '-pix_fmt', config['pix_fmt'],
            '-movflags', '+faststart',
            *audio_params,
            '-progress', '-',
            '-f', 'mp4',
            temp_output_path
        ]

    def build_gpu_cmd():
        return [
            'ffmpeg', '-y', '-nostdin',
            '-hwaccel', 'vaapi',
            '-hwaccel_device', gpu_device,
            '-hwaccel_output_format', 'vaapi',
            '-i', input_path,
            '-vf', 'scale_vaapi=w=iw:h=ih,format=nv12|vaapi',
            '-c:v', 'h264_vaapi',
            *audio_params,
            '-movflags', '+faststart',
            '-progress', '-',
            '-f', 'mp4',
            temp_output_path
        ]

    # Verificar disponibilidad del device GPU
    if use_gpu and not os.path.exists(gpu_device):
        logger.warning(f"[GPU] Dispositivo {gpu_device} no existe. Usando CPU como fallback.")
        use_gpu = False

    cmd = build_gpu_cmd() if use_gpu else build_cpu_cmd()
    mode_label = f"GPU VAAPI ({gpu_device})" if use_gpu else "CPU (libx264)"
    logger.info(f"Iniciando transcodificacion [{mode_label}]: {input_path}")

    def _run_ffmpeg(cmd_to_run):
        process = subprocess.Popen(
            cmd_to_run,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
            errors='replace'
        )
        if task_id:
            with processor.lock:
                if task_id in processor.active_tasks:
                    processor.active_tasks[task_id]['process'] = process
        output_lines = []
        for line in process.stdout:
            line = line.strip()
            output_lines.append(line)
            if not line:
                continue
            if total_duration > 0 and 'out_time_ms' in line:
                try:
                    current_time_us = int(line.split('=')[1].strip())
                    progress = min(99, int((current_time_us / (total_duration * 1000000)) * 100))
                    if task_id:
                        with processor.lock:
                            if task_id in processor.active_tasks:
                                if progress > processor.active_tasks[task_id].get('progress', 0):
                                    processor.active_tasks[task_id]['progress'] = progress
                except (ValueError, IndexError):
                    pass
        process.wait()
        return process.returncode, output_lines

    try:
        returncode, output_lines = _run_ffmpeg(cmd)

        # Fallback a CPU si GPU fallo
        if returncode != 0 and use_gpu:
            logger.warning(f"[GPU] Fallo la transcodificacion GPU (codigo {returncode}). Reintentando con CPU...")
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)
            returncode, output_lines = _run_ffmpeg(build_cpu_cmd())
            mode_label = "CPU-fallback (libx264)"

        if returncode != 0:
            full_output = "\n".join(output_lines)
            error_msg = f"Error en la transcodificacion (codigo {returncode}).\nSalida FFmpeg:\n{full_output[-2000:]}"
            logger.error(error_msg)
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)
            return {'success': False, 'error': error_msg, 'returncode': returncode}

        if not os.path.exists(temp_output_path) or os.path.getsize(temp_output_path) == 0:
            error_msg = "El archivo de salida temporal no se creo o esta vacio."
            logger.error(error_msg)
            return {'success': False, 'error': error_msg, 'returncode': -1}

        os.rename(temp_output_path, output_path)
        logger.info(f"Transcodificacion completada [{mode_label}]: {output_path}")
        return {
            'success': True,
            'output_path': output_path,
            'size': os.path.getsize(output_path),
            'duration': get_video_duration(output_path)
        }

    except Exception as e:
        error_msg = f"Error inesperado en la transcodificacion: {str(e)}"
        logger.error(error_msg, exc_info=True)
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)
        return {'success': False, 'error': error_msg, 'exception': str(e)}


def get_video_duration(file_path):
    """Obtiene la duración de un video en segundos."""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
             '-of', 'default=noprint_wrappers=1:nokey=1', file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return float(result.stdout.strip())
    except Exception as e:
        logger.error(f"Error al obtener duración de {file_path}: {str(e)}")
        return 0

# Instancia global del procesador de video
video_processor = VideoProcessor()

# Limpieza al cerrar la aplicación
import atexit
atexit.register(video_processor.stop_workers)
