# API REST de Signally para Aplicaciones Móviles

Esta API permite que aplicaciones móviles (como Signally Mobile) se conecten y gestionen canales, archivos y transcodificación en un servidor Signally.

## Base URL

```
http://IP_SERVIDOR:5000/api
```

Ejemplo: `http://172.16.1.40:5000/api`

---

## Endpoints de Canales

### 1. Obtener todos los canales

**GET** `/api/canales`

Devuelve una lista JSON con todos los canales configurados en el servidor.

**Respuesta (200 OK):**
```json
[
  {
    "id": 1,
    "nombre": "Sala de espera",
    "tipo_contenido": "video",
    "rotacion": 0,
    "repeticion": "bucle",
    "contenidos": ["video1.mp4", "video2.mp4"],
    "proceso_ffmpeg": null,
    "en_transmision": false,
    "fecha_creacion": "2024-01-15T10:30:00",
    "fecha_actualizacion": "2024-01-15T10:30:00"
  }
]
```

### 2. Obtener un canal específico

**GET** `/api/canales/<canal_id>`

Obtiene los detalles de un canal específico por ID.

**Ejemplo:** `GET /api/canales/1`

**Respuesta (200 OK):**
```json
{
  "id": 1,
  "nombre": "Sala de espera",
  "tipo_contenido": "video",
  "rotacion": 0,
  "repeticion": "bucle",
  "contenidos": ["video1.mp4", "video2.mp4"],
  "proceso_ffmpeg": null,
  "en_transmision": false,
  "fecha_creacion": "2024-01-15T10:30:00",
  "fecha_actualizacion": "2024-01-15T10:30:00"
}
```

### 3. Crear o actualizar un canal

**POST** `/api/canales/guardar`

Crea un nuevo canal o actualiza uno existente.

**Body (JSON):**
```json
{
  "id": null,
  "nombre": "Sala de espera",
  "tipoContenido": "video",
  "rotacion": 0,
  "repeticion": "bucle",
  "contenidos": ["video1.mp4", "video2.mp4"]
}
```

**Para actualizar, incluir el ID:**
```json
{
  "id": 1,
  "nombre": "Sala de espera actualizada",
  "tipoContenido": "imagen",
  "rotacion": 90,
  "repeticion": "once",
  "contenidos": ["imagen1.jpg"]
}
```

**Respuesta (200 OK):**
```json
{
  "success": true,
  "message": "Canal guardado correctamente",
  "canal": {
    "id": 1,
    "nombre": "Sala de espera",
    ...
  }
}
```

### 4. Eliminar un canal

**POST** `/api/canales/eliminar/<canal_id>`

Elimina un canal del servidor.

**Ejemplo:** `POST /api/canales/eliminar/1`

**Respuesta (200 OK):**
```json
{
  "success": true,
  "message": "Canal eliminado correctamente"
}
```

---

## Endpoints de Archivos

### 1. Obtener lista de archivos

**GET** `/api/archivos`

Devuelve la lista de archivos multimedia disponibles en el servidor.

**Respuesta (200 OK):**
```json
[
  {
    "nombre": "video1.mp4",
    "tipo": "video",
    "tamano": 524288000,
    "estado": "completado",
    "transcodificado": true
  },
  {
    "nombre": "imagen1.jpg",
    "tipo": "imagen",
    "tamano": 2097152,
    "estado": "pendiente",
    "transcodificado": false
  }
]
```

**Campos:**
- `nombre`: Nombre del archivo
- `tipo`: video, imagen, audio o archivo
- `tamano`: Tamaño en bytes
- `estado`: completado, procesando, pendiente
- `transcodificado`: true si el video ya está en formato MP4 optimizado

---

## Endpoints de Transcodificación

### 1. Obtener estado de transcodificación

**GET** `/api/transcoding/status/<filename>`

Obtiene el estado actual de la transcodificación de un archivo.

**Ejemplo:** `GET /api/transcoding/status/video1.mp4`

**Respuesta cuando está procesando (200 OK):**
```json
{
  "success": true,
  "task_id": "task_123",
  "status": "processing",
  "progress": 65,
  "started_at": "2024-01-15T10:30:00",
  "filename": "video1.mp4"
}
```

**Respuesta cuando está completado (200 OK):**
```json
{
  "success": true,
  "status": "completed",
  "filename": "video1.mp4",
  "transcoded_path": "/multimedia/transcodificados/video1.mp4",
  "size": 314572800
}
```

**Respuesta cuando está pendiente (200 OK):**
```json
{
  "success": true,
  "status": "pending",
  "filename": "video1.mp4",
  "message": "No hay tarea de transcodificación en curso para este archivo"
}
```

---

## Tipos de Contenido

Los canales pueden ser de los siguientes tipos:

- `video`: Para reproducir videos (MP4, MOV, AVI, MKV)
- `imagen`: Para mostrar imágenes (JPG, PNG, GIF)
- `streaming`: Para streaming RTMP/HLS

## Modos de Repetición

- `bucle`: Reproduce el contenido en bucle infinito
- `once`: Reproduce el contenido una sola vez
- `random`: Reproduce el contenido de forma aleatoria

## Rotación de Pantalla

- `0`: Sin rotación (paisaje)
- `90`: Rotación 90 grados
- `180`: Rotación 180 grados
- `270`: Rotación 270 grados

---

## Códigos de Error

| Código | Descripción |
|--------|-------------|
| 200 | OK - Solicitud exitosa |
| 400 | Bad Request - Datos inválidos |
| 404 | Not Found - Recurso no encontrado |
| 500 | Internal Server Error - Error del servidor |

---

## Ejemplos de Uso (cURL)

### Obtener todos los canales
```bash
curl http://172.16.1.40:5000/api/canales
```

### Crear un canal
```bash
curl -X POST http://172.16.1.40:5000/api/canales/guardar \
  -H "Content-Type: application/json" \
  -d '{
    "id": null,
    "nombre": "Sala de espera",
    "tipoContenido": "video",
    "rotacion": 0,
    "repeticion": "bucle",
    "contenidos": ["video1.mp4"]
  }'
```

### Obtener lista de archivos
```bash
curl http://172.16.1.40:5000/api/archivos
```

### Obtener estado de transcodificación
```bash
curl http://172.16.1.40:5000/api/transcoding/status/video1.mp4
```

---

## Notas Importantes

1. La API siempre responde en formato JSON
2. Los errores incluyen un campo `error` con la descripción del problema
3. Los IDs de canales son números enteros generados automáticamente
4. Los nombres de archivo deben incluir la extensión
5. Los cambios en canales se guardan automáticamente en el archivo `canales.json`

