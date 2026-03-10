#!/bin/bash
# Script de instalación rápida de dependencias Python
# Úsalo si ya tienes el venv creado pero faltan las dependencias

echo "=== Instalación de Dependencias de Signally ==="
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "requirements.txt" ]; then
    echo "Error: No se encontró requirements.txt"
    echo "Asegúrate de ejecutar este script desde el directorio raíz del proyecto"
    exit 1
fi

# Crear venv si no existe
if [ ! -d "venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv venv
    echo "✓ Entorno virtual creado"
else
    echo "✓ Entorno virtual ya existe"
fi

# Activar entorno virtual
echo ""
echo "Activando entorno virtual..."
source venv/bin/activate

# Actualizar pip
echo ""
echo "Actualizando pip..."
pip install --upgrade pip

# Instalar dependencias
echo ""
echo "Instalando dependencias desde requirements.txt..."
pip install -r requirements.txt

# Verificar instalación
echo ""
echo "=== Verificando instalación ==="
python -c "import flask; print(f'✓ Flask {flask.__version__} instalado correctamente')"

if [ $? -eq 0 ]; then
    echo ""
    echo "=== Instalación completada exitosamente ==="
    echo ""
    echo "Para activar el entorno virtual:"
    echo "  source venv/bin/activate"
    echo ""
    echo "Para iniciar la aplicación:"
    echo "  python wsgi.py"
    echo "  o"
    echo "  gunicorn --bind 0.0.0.0:5000 wsgi:application"
else
    echo ""
    echo "✗ Hubo un error en la instalación"
    exit 1
fi
