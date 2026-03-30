#!/bin/bash
# Script de instalación de dependencias de Signally
# Instala dependencias del sistema (ffmpeg, vainfo, pciutils) y del entorno Python

set -e

echo "=== Instalación de Dependencias de Signally ==="
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "requirements.txt" ]; then
    echo "Error: No se encontró requirements.txt"
    echo "Asegúrate de ejecutar este script desde el directorio raíz del proyecto"
    exit 1
fi

# ── Dependencias del sistema ───────────────────────────────────────────────────
echo "=== Instalando dependencias del sistema ==="

SYS_DEPS=(ffmpeg ffprobe vainfo pciutils)
MISSING=()

for dep in "${SYS_DEPS[@]}"; do
    if ! command -v "$dep" &>/dev/null; then
        MISSING+=("$dep")
    else
        echo "✓ $dep ya está instalado"
    fi
done

if [ ${#MISSING[@]} -gt 0 ]; then
    echo ""
    echo "Faltan dependencias del sistema: ${MISSING[*]}"
    echo "Instalando con apt..."

    # Mapear comandos a paquetes apt
    APT_PACKAGES=()
    for dep in "${MISSING[@]}"; do
        case "$dep" in
            ffmpeg|ffprobe) APT_PACKAGES+=("ffmpeg") ;;
            vainfo)         APT_PACKAGES+=("vainfo") ;;
            pciutils)       APT_PACKAGES+=("pciutils") ;;
        esac
    done

    # Eliminar duplicados
    APT_PACKAGES=($(echo "${APT_PACKAGES[@]}" | tr ' ' '\n' | sort -u | tr '\n' ' '))

    if command -v sudo &>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y "${APT_PACKAGES[@]}"
    else
        apt-get update -qq && apt-get install -y "${APT_PACKAGES[@]}"
    fi

    # Verificar que se instalaron correctamente
    for dep in ffmpeg ffprobe; do
        if command -v "$dep" &>/dev/null; then
            echo "✓ $dep instalado: $(which $dep)"
        else
            echo "✗ ERROR: $dep no se pudo instalar. La transcodificación no funcionará."
            echo "  Instálalo manualmente: apt install ffmpeg"
            exit 1
        fi
    done
    echo "✓ vainfo y pciutils instalados (detección de GPU)"
fi

echo ""

# ── Entorno virtual Python ─────────────────────────────────────────────────────
echo "=== Configurando entorno Python ==="

if [ ! -d "venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv venv
    echo "✓ Entorno virtual creado"
else
    echo "✓ Entorno virtual ya existe"
fi

source venv/bin/activate

echo "Actualizando pip..."
pip install --upgrade pip -q

echo "Instalando dependencias Python..."
pip install -r requirements.txt -q

# ── Verificación final ─────────────────────────────────────────────────────────
echo ""
echo "=== Verificación final ==="

python -c "import flask; print(f'✓ Flask {flask.__version__}')" || { echo "✗ Error instalando Flask"; exit 1; }
ffmpeg -version 2>&1 | head -1 | sed 's/^/✓ /'
ffprobe -version 2>&1 | head -1 | sed 's/^/✓ /'
command -v vainfo  &>/dev/null && echo "✓ vainfo disponible"  || echo "⚠  vainfo no disponible (detección GPU limitada)"
command -v lspci   &>/dev/null && echo "✓ lspci disponible"   || echo "⚠  lspci no disponible (detección GPU limitada)"

echo ""
echo "=== Instalación completada ==="
echo ""
echo "Para iniciar la aplicación:"
echo "  source venv/bin/activate"
echo "  python wsgi.py"
echo "  o"
echo "  gunicorn --bind 0.0.0.0:5000 wsgi:application"
