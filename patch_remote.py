
import re

with open('routes_remote.py', 'r') as f:
    content = f.read()

# 1. Corregir get_video_stream_params
old_gvsp = r'def get_video_stream_params\(bitrate=2500, force_cpu=False\):.*?return hw_args, video_args, use_gpu'
new_gvsp = """def get_video_stream_params(bitrate=2500, force_cpu=False):
    \"\"\"Retorna los parametros de codificacion segun la configuracion de GPU.\"\"\"
    from .config_manager import config_manager
    video_cfg = config_manager.get_video_config()
    use_gpu = video_cfg.get('hardware_accel') == 'gpu' and not force_cpu
    # Forzar renderD128 para Intel si existe, ya que renderD129 (AMD) no codifica
    gpu_device = video_cfg.get('gpu_device', '/dev/dri/renderD128')
    
    hw_args = []
    if use_gpu:
        hw_args = ['-vaapi_device', gpu_device]
        video_args = [
            '-c:v', 'h264_vaapi',
            '-profile:v', 'constrained_baseline',
            '-b:v', f'{bitrate}k',
            '-maxrate', f'{bitrate}k',
            '-bufsize', f'{bitrate*2}k',
            '-g', '60'
        ]
    else:
        video_args = [
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-tune', 'zerolatency',
            '-b:v', f'{bitrate}k',
            '-maxrate', f'{bitrate}k',
            '-bufsize', f'{bitrate*2}k',
            '-g', '60',
            '-pix_fmt', 'yuv420p'
        ]
    return hw_args, video_args, use_gpu"""

content = re.sub(old_gvsp, new_gvsp, content, flags=re.DOTALL)

# 2. Corregir la construcción de comandos dinámicos (Playlist, Bucles, etc.)
# Buscamos el patrón problemático donde se modifica target_cmd pero se corre ffmpeg_cmd,
# o donde se olvidan los parámetros de salida.

# Patrón para la inyección de GPU que está fallando en el remoto
dynamic_gpu_pattern = r'# Parametros de video \(GPU/CPU\).*?rtmp_url if \'rtmp_url\' in locals\(\) else \(rtmp_server \+ \'/live/\' \+ nombre_stream\)\s+\]\)'

# Reemplazo robusto
unified_cmd_logic = """# Parametros de video (GPU/CPU)
            hw_args, video_args, use_gpu = get_video_stream_params()
            # SELECCIÓN CRÍTICA: Usar la lista de comando correcta
            current_target = cmd if 'cmd' in locals() else ffmpeg_cmd
            
            if use_gpu:
                # Insertar hw_args al principio
                for i, arg in enumerate(hw_args):
                    current_target.insert(i+1, arg)
                
                # Adaptar o crear filtros para GPU
                vf_exists = False
                for idx, item in enumerate(current_target):
                    if item == '-vf':
                        current_target[idx+1] = f"{current_target[idx+1]},format=nv12,hwupload"
                        vf_exists = True
                        break
                if not vf_exists:
                    try:
                        idx_i = current_target.index('-i')
                        current_target.insert(idx_i + 2, '-vf')
                        current_target.insert(idx_i + 3, 'format=nv12,hwupload')
                    except: pass

            # Agregar parametros de codificacion y SALIDA (Audio/RTMP)
            current_target.extend(video_args)
            current_target.extend([
                '-c:a', 'aac',
                '-b:a', '192k',
                '-ar', '44100',
                '-ac', '2',
                '-f', 'flv',
                rtmp_url if 'rtmp_url' in locals() else (rtmp_server + '/live/' + (nombre_stream if 'nombre_stream' in locals() else 'stream'))
            ])
            
            # ASEGURAR que el Popen usará el comando extendido
            if 'cmd' in locals(): ffmpeg_cmd = cmd"""

content = re.sub(dynamic_gpu_pattern, unified_cmd_logic, content, flags=re.DOTALL)

# 3. Corregir el bloque estático de iniciar_transmision_canal (CPU fallback)
# Este bloque es más específico.

static_gpu_pattern = r'if video_cfg\.get\(\'hardware_accel\'\) == \'gpu\':.*?rtmp_url\s+\]\s+\)'
new_static_block = """# Configuración de codificación (GPU/CPU)
            hw_args, video_params, use_gpu = get_video_stream_params(bitrate=bitrate)
            
            if use_gpu:
                # Insertar hw_args al principio
                for i, arg in enumerate(hw_args):
                    ffmpeg_cmd.insert(i+1, arg)
                
                # Adaptar filtros para GPU
                for idx, item in enumerate(ffmpeg_cmd):
                    if item == '-vf':
                        ffmpeg_cmd[idx+1] = f"{ffmpeg_cmd[idx+1]},format=nv12,hwupload"
                        break
            
            ffmpeg_cmd.extend(video_params)
            
            # Parametros comunes de salida
            ffmpeg_cmd.extend([
                '-c:a', 'aac',
                '-b:a', '192k',
                '-ar', '44100',
                '-ac', '2',
                '-f', 'flv',
                rtmp_url
            ])"""

content = re.sub(static_gpu_pattern, new_static_block, content, flags=re.DOTALL)

with open('routes_fixed.py', 'w') as f:
    f.write(content)
print("Transformación completada.")
