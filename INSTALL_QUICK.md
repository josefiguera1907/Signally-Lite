# Instalación Rápida de Signally

## Solución Rápida: Error "ModuleNotFoundError: No module named 'flask'"

Si ya ejecutaste `setup.py` pero te sale el error de que no encuentra Flask, es porque las dependencias no se instalaron correctamente en el entorno virtual.

### Opción 1: Script de Instalación Rápida (Recomendado)

```bash
# Ejecutar el script de instalación de dependencias
./install_deps.sh
```

### Opción 2: Instalación Manual

```bash
# 1. Activar el entorno virtual
source venv/bin/activate

# 2. Actualizar pip
pip install --upgrade pip

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Verificar instalación
python -c "import flask; print('Flask instalado correctamente')"
```

### Opción 3: Recrear Entorno Virtual desde Cero

```bash
# 1. Eliminar el entorno virtual actual
rm -rf venv

# 2. Crear nuevo entorno virtual
python3 -m venv venv

# 3. Activar el entorno virtual
source venv/bin/activate

# 4. Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt
```

## Iniciar la Aplicación

Una vez instaladas las dependencias:

```bash
# Activar entorno virtual (si no está activado)
source venv/bin/activate

# Opción 1: Modo desarrollo
python wsgi.py

# Opción 2: Modo producción
gunicorn --bind 0.0.0.0:5000 wsgi:application
```

## Verificar que Todo Funciona

```bash
# Con el entorno virtual activado:
python -c "
import flask
import werkzeug
import ffmpeg
print('✓ Todas las dependencias principales instaladas')
print(f'  Flask: {flask.__version__}')
print(f'  Werkzeug: {werkzeug.__version__}')
"
```

## Problemas Comunes

### Error: "No se encuentra el módulo X"
**Solución:** Asegúrate de tener activado el entorno virtual:
```bash
source venv/bin/activate
```

### Error: "Permission denied"
**Solución:** Dale permisos de ejecución al script:
```bash
chmod +x install_deps.sh
```

### Error al instalar dependencias
**Solución:** Instala las dependencias del sistema primero:
```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv python3-dev build-essential
```

## Instalación Completa desde Cero

Si quieres hacer la instalación completa con Nginx, RTMP, etc.:

```bash
sudo python3 setup.py
```

Esto instalará:
- ✓ Dependencias del sistema (FFmpeg, Nginx, etc.)
- ✓ Entorno virtual de Python
- ✓ Dependencias de Python
- ✓ Estructura de directorios
- ✓ Configuración de Nginx con RTMP
- ✓ FileBrowser
- ✓ Configuración de firewall
