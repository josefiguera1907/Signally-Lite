from flask import Blueprint, jsonify, current_app, request
import os
from .video_processor import video_processor
from .models import Canal
from .api_key_manager import APIKeyManager
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps

api_bp = Blueprint('api', __name__)

# ==================== MIDDLEWARE DE AUTENTICACIÓN ====================

def require_api_key(f):
    """Decorador para requerir API key en endpoints protegidos."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')

        if not api_key:
            return jsonify({'error': 'API key requerida'}), 401

        if not APIKeyManager.validar_api_key(api_key):
            return jsonify({'error': 'API key inválida o desactivada'}), 403

        return f(*args, **kwargs)

    return decorated_function

# ==================== CANALES ====================

@api_bp.route('/canales', methods=['GET'])
def api_get_canales():
    """Endpoint JSON que devuelve todos los canales. Para uso en aplicaciones móviles."""
    try:
        canales = Canal.cargar_todos()
        return jsonify([canal.to_dict() for canal in canales])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/canales/<int:canal_id>', methods=['GET'])
def api_get_canal(canal_id):
    """Obtiene un canal específico por ID."""
    try:
        canal = Canal.obtener_por_id(canal_id)
        if not canal:
            return jsonify({'error': 'Canal no encontrado'}), 404
        return jsonify(canal.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/canales/guardar', methods=['POST'])
def api_guardar_canal():
    """Crea o actualiza un canal."""
    try:
        data = request.get_json()

        # Validación básica
        if not data or not data.get('nombre') or not data.get('tipoContenido'):
            return jsonify({'error': 'Faltan campos requeridos: nombre, tipoContenido'}), 400

        canal_id = data.get('id')

        if canal_id:
            # Actualizar canal existente
            canal = Canal.obtener_por_id(int(canal_id))
            if not canal:
                return jsonify({'error': 'Canal no encontrado'}), 404

            canal.nombre = data.get('nombre')
            canal.tipo_contenido = data.get('tipoContenido')
            canal.rotacion = int(data.get('rotacion', 0))
            canal.repeticion = data.get('repeticion', 'bucle')
            canal.contenidos = data.get('contenidos', [])
            canal.fecha_actualizacion = datetime.now().isoformat()
        else:
            # Crear nuevo canal
            canal = Canal(
                nombre=data.get('nombre'),
                tipo_contenido=data.get('tipoContenido'),
                rotacion=int(data.get('rotacion', 0)),
                repeticion=data.get('repeticion', 'bucle'),
                contenidos=data.get('contenidos', [])
            )

        Canal.guardar(canal)
        return jsonify({
            'success': True,
            'message': 'Canal guardado correctamente',
            'canal': canal.to_dict()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/canales/eliminar/<int:canal_id>', methods=['POST'])
def api_eliminar_canal(canal_id):
    """Elimina un canal."""
    try:
        canal = Canal.obtener_por_id(canal_id)
        if not canal:
            return jsonify({'error': 'Canal no encontrado'}), 404

        Canal.eliminar_por_id(canal_id)
        return jsonify({'success': True, 'message': 'Canal eliminado correctamente'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== ARCHIVOS ====================

def obtener_archivos_multimedia():
    """Obtiene la lista de archivos multimedia disponibles."""
    archivos = []
    processed_names = set()

    try:
        # Primero verificar archivos transcodificados
        transcoded_folder = current_app.config['TRANSCODED_FOLDER']
        original_folder = current_app.config['ORIGINAL_FOLDER']

        VIDEO_EXTENSIONS = ['mp4', 'mov', 'avi', 'mkv', 'flv', 'wmv', 'webm']
        IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
        AUDIO_EXTENSIONS = ['mp3', 'wav', 'aac', 'flac', 'm4a']

        for filename in os.listdir(transcoded_folder):
            if not filename.lower().endswith('.mp4'):
                continue

            base_name = os.path.splitext(filename)[0]
            original_name = None

            for ext in VIDEO_EXTENSIONS:
                possible_original = f"{base_name}.{ext}"
                if os.path.exists(os.path.join(original_folder, possible_original)):
                    original_name = possible_original
                    break

            if not original_name:
                continue

            filepath = os.path.join(transcoded_folder, filename)
            processed_names.add(original_name)

            archivos.append({
                'nombre': original_name,
                'tipo': 'video',
                'tamano': os.path.getsize(filepath),
                'estado': 'completado',
                'transcodificado': True
            })

        # Luego agregar archivos originales sin versión transcodificada
        for filename in os.listdir(original_folder):
            if filename in processed_names:
                continue

            filepath = os.path.join(original_folder, filename)
            if not os.path.isfile(filepath):
                continue

            _, ext = os.path.splitext(filename)
            ext = ext[1:].lower() if ext else ''

            is_processing = any(
                task.get('filename') == filename and task.get('status') == 'processing'
                for task in video_processor.active_tasks.values()
            )

            status = 'procesando' if is_processing else 'pendiente'

            if ext in VIDEO_EXTENSIONS:
                tipo = 'video'
            elif ext in IMAGE_EXTENSIONS:
                tipo = 'imagen'
            elif ext in AUDIO_EXTENSIONS:
                tipo = 'audio'
            else:
                tipo = 'archivo'

            archivos.append({
                'nombre': filename,
                'tipo': tipo,
                'tamano': os.path.getsize(filepath),
                'estado': status,
                'transcodificado': False
            })

    except Exception as e:
        print(f"Error al obtener archivos: {str(e)}")

    archivos.sort(key=lambda x: x.get('nombre'))
    return archivos

@api_bp.route('/archivos', methods=['GET'])
def api_get_archivos():
    """Obtiene la lista de archivos multimedia disponibles."""
    try:
        archivos = obtener_archivos_multimedia()
        return jsonify(archivos)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== TRANSCODIFICACIÓN ====================

@api_bp.route('/transcoding/status/<filename>')
def get_transcoding_status(filename):
    """Obtiene el estado de transcodificación de un archivo.
    
    Args:
        filename: Nombre del archivo a verificar
        
    Returns:
        JSON con el estado de transcodificación
    """
    # Verificar si el archivo existe en la carpeta de originales
    original_path = os.path.join(current_app.config['ORIGINAL_FOLDER'], filename)
    if not os.path.exists(original_path):
        return jsonify({
            'success': False,
            'error': 'Archivo no encontrado',
            'filename': filename
        }), 404
    
    # Verificar si hay una tarea de transcodificación en curso
    task_info = None
    for task_id, task in video_processor.active_tasks.items():
        if task.get('filename') == filename:
            task_info = {
                'task_id': task_id,
                'status': 'processing',
                'progress': task.get('progress', 0),
                'started_at': task.get('started_at'),
                'filename': filename
            }
            break
    
    # Si no hay tarea en curso, verificar si existe la versión transcodificada
    if not task_info:
        name, ext = os.path.splitext(filename)
        transcoded_path = os.path.join(current_app.config['TRANSCODED_FOLDER'], f"{name}.mp4")
        
        if os.path.exists(transcoded_path):
            return jsonify({
                'success': True,
                'status': 'completed',
                'filename': filename,
                'transcoded_path': transcoded_path,
                'size': os.path.getsize(transcoded_path)
            })
        else:
            return jsonify({
                'success': True,
                'status': 'pending',
                'filename': filename,
                'message': 'No hay tarea de transcodificación en curso para este archivo'
            })
    
    return jsonify({
        'success': True,
        **task_info
    })

# ==================== API KEYS ====================

@api_bp.route('/api-keys', methods=['GET'])
def get_api_keys():
    """Obtiene la lista de todas las API keys del usuario."""
    try:
        keys = APIKeyManager.obtener_api_keys()
        return jsonify({
            'success': True,
            'api_keys': keys
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api-keys/generar', methods=['POST'])
def generate_api_key():
    """Genera una nueva API key."""
    try:
        data = request.get_json() or {}
        nombre = data.get('nombre', 'API Key')

        nueva_key = APIKeyManager.generar_api_key(nombre)

        return jsonify({
            'success': True,
            'message': 'API key generada correctamente',
            'api_key': nueva_key['api_key'],
            'id': nueva_key['id'],
            'nombre': nueva_key['nombre'],
            'creada_en': nueva_key['creada_en'],
            'advertencia': 'Guarda esta key en un lugar seguro. No podrás verla de nuevo.'
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api-keys/<key_id>', methods=['DELETE'])
def delete_api_key(key_id):
    """Elimina una API key."""
    try:
        if APIKeyManager.eliminar_api_key(key_id):
            return jsonify({
                'success': True,
                'message': 'API key eliminada correctamente'
            })
        else:
            return jsonify({'error': 'API key no encontrada'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api-keys/<key_id>/desactivar', methods=['POST'])
def deactivate_api_key(key_id):
    """Desactiva una API key."""
    try:
        if APIKeyManager.desactivar_api_key(key_id):
            return jsonify({
                'success': True,
                'message': 'API key desactivada correctamente'
            })
        else:
            return jsonify({'error': 'API key no encontrada'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/api-keys/<key_id>/activar', methods=['POST'])
def activate_api_key(key_id):
    """Activa una API key previamente desactivada."""
    try:
        if APIKeyManager.activar_api_key(key_id):
            return jsonify({
                'success': True,
                'message': 'API key activada correctamente'
            })
        else:
            return jsonify({'error': 'API key no encontrada'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== CONFIGURACIÓN M3U ====================

@api_bp.route('/config/m3u', methods=['GET'])
def get_m3u_config():
    """Obtiene la configuración actual de URL M3U."""
    try:
        from .config_manager import config_manager
        config = config_manager.get_m3u_config()
        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/config/m3u', methods=['POST'])
def set_m3u_config():
    """Actualiza la configuración de URL M3U."""
    try:
        from .config_manager import config_manager
        data = request.get_json()

        url_path = data.get('url_path')
        custom_base = data.get('custom_base')

        success, message = config_manager.set_m3u_config(url_path=url_path, custom_base=custom_base)

        if success:
            # Construir la URL de ejemplo
            example_url = config_manager.build_m3u_url(request.host)
            return jsonify({
                'success': True,
                'message': message,
                'example_url': example_url,
                'config': config_manager.get_m3u_config()
            })
        else:
            return jsonify({'error': message}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== CONFIGURACIÓN DE NGINX ====================

@api_bp.route('/config/nginx/status', methods=['GET'])
def get_nginx_status():
    """Obtiene el estado de la configuración de Nginx."""
    try:
        from .nginx_manager import nginx_manager
        status = nginx_manager.get_status()
        return jsonify({
            'success': True,
            'status': status
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/config/nginx/configure', methods=['POST'])
def configure_nginx():
    """Configura Nginx con los server_names especificados."""
    try:
        from .nginx_manager import nginx_manager
        data = request.get_json()

        server_names = data.get('server_names', [])

        if not server_names:
            return jsonify({'error': 'Se requiere al menos un server_name'}), 400

        success, message = nginx_manager.create_nginx_config(server_names=server_names)

        if success:
            return jsonify({
                'success': True,
                'message': message,
                'status': nginx_manager.get_status()
            })
        else:
            return jsonify({'error': message}), 500

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==================== CONFIGURACIÓN DE VIDEO / GPU ====================

def _get_lspci_gpus():
    """Usa lspci para obtener la lista de GPUs con nombre comercial completo.

    Retorna un dict mapeando PCI address (ej: '0000:01:00.0') → dict con
    'pci_name', 'vendor', 'pci_id'.
    """
    import subprocess, re
    pci_gpus = {}
    GPU_CLASSES = {'VGA compatible controller', '3D controller', 'Display controller',
                   'Display adapter'}
    try:
        result = subprocess.run(
            ['lspci', '-mm', '-D'],  # -mm = machine readable, -D = show domain
            capture_output=True, text=True, timeout=8
        )
        if result.returncode != 0:
            return pci_gpus

        # Cada línea: SlotAddr "Class" "Vendor" "Device" "SVendor" "SDevice" "Rev"
        # Ejemplo: 0000:01:00.0 "VGA compatible controller" "NVIDIA" "GeForce RTX 3060" ...
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = re.split(r'\s+"', line, maxsplit=1)
            if len(parts) < 2:
                continue
            pci_addr = parts[0].strip()
            rest = '"' + parts[1]
            # Extraer campos entre comillas
            fields = re.findall(r'"([^"]*)"', rest)
            if len(fields) < 3:
                continue
            pci_class, vendor_name, device_name = fields[0], fields[1], fields[2]

            # Filtrar solo GPUs
            if not any(cls in pci_class for cls in GPU_CLASSES):
                continue

            # Determinar vendor normalizado
            vendor_lower = vendor_name.lower()
            if 'advanced micro' in vendor_lower or ' amd' in vendor_lower or vendor_lower.startswith('amd'):
                vendor = 'AMD'
            elif 'intel' in vendor_lower:
                vendor = 'Intel'
            elif 'nvidia' in vendor_lower:
                vendor = 'NVIDIA'
            else:
                vendor = vendor_name.split()[0] if vendor_name else 'GPU'

            pci_gpus[pci_addr] = {
                'pci_name': f"{vendor_name} {device_name}".strip(),
                'vendor': vendor,
                'pci_id': pci_addr,
            }
    except FileNotFoundError:
        pass  # lspci no disponible, se usa fallback
    except Exception:
        pass
    return pci_gpus


def _get_render_pci_addr(render_dev):
    """Obtiene el PCI address del dispositivo renderD* leyendo sysfs.

    Ejemplo: /dev/dri/renderD128 → '0000:01:00.0'
    """
    import os, re
    try:
        dev_num = re.search(r'renderD(\d+)', render_dev)
        if not dev_num:
            return None
        # Formato sysfs: /sys/class/drm/renderD128/device -> ../../../../0000:01:00.0
        sysfs_path = f"/sys/class/drm/renderD{dev_num.group(1)}/device"
        if not os.path.exists(sysfs_path):
            return None
        link_target = os.readlink(sysfs_path)
        # El último componente del symlink es el PCI address
        pci_addr = os.path.basename(link_target)
        # Normalizar: algunos sistemas omiten el dominio, agregar '0000:' si falta
        if re.match(r'^[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9a-fA-F]$', pci_addr):
            return pci_addr
        # Sin dominio (ej: '01:00.0') → agregar dominio 0000
        if re.match(r'^[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-9a-fA-F]$', pci_addr):
            return f'0000:{pci_addr}'
    except Exception:
        pass
    return None


def detect_gpus():
    """Detecta GPUs disponibles combinando lspci (nombre real) y vainfo (soporte VAAPI).

    Para cada /dev/dri/renderD* encontrado:
    1. Cruza el nodo DRM con el bus PCI via sysfs para obtener el PCI address.
    2. Busca ese PCI address en la salida de lspci para el nombre comercial completo.
    3. Consulta vainfo para verificar soporte VAAPI y codificación H.264.

    Retorna lista de dicts con: device, name, pci_name, vendor, pci_id, driver,
    supported, h264_encode, error.
    """
    import subprocess, re, glob
    gpus = []
    render_devices = sorted(glob.glob('/dev/dri/renderD*'))
    if not render_devices:
        return gpus

    # Obtener info PCI de todas las GPUs del sistema (una sola llamada a lspci)
    pci_gpus = _get_lspci_gpus()

    for device in render_devices:
        dev_num_match = re.search(r'renderD(\d+)', device)
        dev_label = f"renderD{dev_num_match.group(1)}" if dev_num_match else device

        info = {
            'device': device,
            'name': dev_label,          # Fallback si no se detecta nada más
            'pci_name': None,           # Nombre completo de lspci
            'pci_id': None,             # PCI address (ej: 0000:01:00.0)
            'vendor': 'GPU',
            'driver': '',
            'supported': False,
            'h264_encode': False,
            'error': None
        }

        # ── Cruzar con lspci ────────────────────────────────────────────────
        pci_addr = _get_render_pci_addr(device)
        if pci_addr and pci_addr in pci_gpus:
            pci_info = pci_gpus[pci_addr]
            info['pci_name'] = pci_info['pci_name']
            info['pci_id']   = pci_info['pci_id']
            info['vendor']   = pci_info['vendor']
            info['name']     = f"{pci_info['pci_name']} ({dev_label})"
        elif pci_gpus:
            # Si solo hay una GPU en el sistema y un único renderD*, asumir que es esa
            if len(render_devices) == 1 and len(pci_gpus) == 1:
                pci_addr_key, pci_info = next(iter(pci_gpus.items()))
                info['pci_name'] = pci_info['pci_name']
                info['pci_id']   = pci_info['pci_id']
                info['vendor']   = pci_info['vendor']
                info['name']     = f"{pci_info['pci_name']} ({dev_label})"

        # ── Consultar vainfo ─────────────────────────────────────────────────
        try:
            result = subprocess.run(
                ['vainfo', '--display', 'drm', '--device', device],
                capture_output=True, text=True, timeout=8
            )
            output = result.stdout + result.stderr

            driver_match = re.search(r'Driver version:\s*(.*)', output)
            if driver_match:
                info['driver'] = driver_match.group(1).strip()

                # Si lspci no encontró el nombre, usar el driver de vainfo como fallback
                if not info['pci_name']:
                    driver_str = info['driver']
                    vendor = 'GPU'
                    if any(k in driver_str.lower() for k in ('radeon', 'amd', 'verde', 'navi', 'polaris')):
                        vendor = 'AMD'
                    elif 'intel' in driver_str.lower():
                        vendor = 'Intel'
                    elif 'nvidia' in driver_str.lower():
                        vendor = 'NVIDIA'
                    chip_match = re.search(r'for\s+([A-Z0-9]+(?:\s+[A-Z0-9]+)*)',
                                           driver_str, re.IGNORECASE)
                    chip_name = chip_match.group(1).strip() if chip_match else ''
                    info['vendor'] = vendor
                    info['name']   = f"{vendor} {chip_name} ({dev_label})".strip()

            if 'VAEntrypointEncSlice' in output and 'H264' in output:
                info['h264_encode'] = True
                info['supported'] = True
            elif result.returncode == 0:
                info['supported'] = True

        except FileNotFoundError:
            info['error'] = 'vainfo no instalado'
        except subprocess.TimeoutExpired:
            info['error'] = 'Tiempo de espera agotado'
        except Exception as e:
            info['error'] = str(e)

        gpus.append(info)
    return gpus


@api_bp.route('/config/video', methods=['GET'])
def get_video_config():
    """Obtiene la configuración de aceleración de video y las GPUs disponibles."""
    try:
        from .config_manager import config_manager
        cfg = config_manager.get_video_config()
        gpus = detect_gpus()
        return jsonify({'success': True, 'config': cfg, 'gpus': gpus})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@api_bp.route('/config/video', methods=['POST'])
def set_video_config():
    """Guarda la configuración de aceleración de video (cpu o gpu)."""
    try:
        from .config_manager import config_manager
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No se recibieron datos'}), 400
        hardware_accel = data.get('hardware_accel', 'cpu')
        gpu_device = data.get('gpu_device')
        success, message = config_manager.set_video_config(hardware_accel, gpu_device)
        if success:
            return jsonify({'success': True, 'message': message, 'config': config_manager.get_video_config()})
        return jsonify({'success': False, 'error': message}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
