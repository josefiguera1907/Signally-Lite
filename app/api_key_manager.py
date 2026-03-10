import os
import json
import secrets
import hashlib
from datetime import datetime
from pathlib import Path


class APIKeyManager:
    """Gestor de API Keys para Signally."""

    _archivo_almacenamiento = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'api_keys.json'
    )

    @classmethod
    def _cargar_keys(cls):
        """Carga todas las API keys del archivo de almacenamiento."""
        try:
            if not os.path.exists(cls._archivo_almacenamiento):
                return {}

            with open(cls._archivo_almacenamiento, 'r') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception as e:
            print(f"Error cargando API keys: {e}")
            return {}

    @classmethod
    def _guardar_keys(cls, keys):
        """Guarda todas las API keys en el archivo de almacenamiento."""
        try:
            os.makedirs(os.path.dirname(cls._archivo_almacenamiento), exist_ok=True)

            # Crear archivo temporal
            temp_file = f"{cls._archivo_almacenamiento}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(keys, f, indent=2)

            # Reemplazar de forma atómica
            if os.path.exists(cls._archivo_almacenamiento):
                os.replace(temp_file, cls._archivo_almacenamiento)
            else:
                os.rename(temp_file, cls._archivo_almacenamiento)
        except Exception as e:
            print(f"Error guardando API keys: {e}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass

    @classmethod
    def generar_api_key(cls, nombre="API Key"):
        """
        Genera una nueva API key.

        Args:
            nombre: Nombre descriptivo para la API key

        Returns:
            dict con los detalles de la nueva API key
        """
        # Generar una key segura de 32 bytes
        key_bytes = secrets.token_bytes(32)
        api_key = secrets.token_urlsafe(32)

        # Crear un hash para almacenar (no almacenamos la key en texto plano)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        # Generar ID único
        key_id = secrets.token_hex(8)

        keys = cls._cargar_keys()

        # Guardar información de la key
        keys[key_id] = {
            'id': key_id,
            'nombre': nombre,
            'hash': key_hash,
            'creada_en': datetime.now().isoformat(),
            'ultima_utilizacion': None,
            'activa': True
        }

        cls._guardar_keys(keys)

        return {
            'id': key_id,
            'nombre': nombre,
            'api_key': api_key,  # Solo se devuelve una vez al crear
            'creada_en': keys[key_id]['creada_en'],
            'activa': True
        }

    @classmethod
    def obtener_api_keys(cls):
        """
        Obtiene la lista de todas las API keys (sin mostrar el valor real).

        Returns:
            Lista de dicts con información de las keys
        """
        keys = cls._cargar_keys()
        resultado = []

        for key_id, info in keys.items():
            resultado.append({
                'id': info['id'],
                'nombre': info['nombre'],
                'creada_en': info['creada_en'],
                'ultima_utilizacion': info['ultima_utilizacion'],
                'activa': info['activa'],
                'vista_previa': f"sk_{key_id[:8]}..."  # Solo mostrar primeros 8 caracteres
            })

        return resultado

    @classmethod
    def validar_api_key(cls, api_key):
        """
        Valida una API key y registra su uso.

        Args:
            api_key: La key a validar

        Returns:
            True si la key es válida y está activa, False en caso contrario
        """
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        keys = cls._cargar_keys()

        for key_id, info in keys.items():
            if info['hash'] == key_hash and info['activa']:
                # Actualizar última utilización
                info['ultima_utilizacion'] = datetime.now().isoformat()
                cls._guardar_keys(keys)
                return True

        return False

    @classmethod
    def eliminar_api_key(cls, key_id):
        """
        Elimina una API key.

        Args:
            key_id: ID de la key a eliminar

        Returns:
            True si se eliminó correctamente, False en caso contrario
        """
        keys = cls._cargar_keys()

        if key_id in keys:
            del keys[key_id]
            cls._guardar_keys(keys)
            return True

        return False

    @classmethod
    def desactivar_api_key(cls, key_id):
        """
        Desactiva una API key (sin eliminarla).

        Args:
            key_id: ID de la key a desactivar

        Returns:
            True si se desactivó correctamente, False en caso contrario
        """
        keys = cls._cargar_keys()

        if key_id in keys:
            keys[key_id]['activa'] = False
            cls._guardar_keys(keys)
            return True

        return False

    @classmethod
    def activar_api_key(cls, key_id):
        """
        Activa una API key previamente desactivada.

        Args:
            key_id: ID de la key a activar

        Returns:
            True si se activó correctamente, False en caso contrario
        """
        keys = cls._cargar_keys()

        if key_id in keys:
            keys[key_id]['activa'] = True
            cls._guardar_keys(keys)
            return True

        return False
