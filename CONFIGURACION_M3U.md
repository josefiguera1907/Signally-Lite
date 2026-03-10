# Configuración de URL M3U - Signally

## Descripción

Esta funcionalidad permite personalizar la URL del archivo M3U que genera Signally, tanto en el nombre del archivo como en la base de la URL (IP o dominio).

## Ubicación

La configuración se encuentra en: **Configuración → Opciones de Configuración → Configuración de URL M3U**

## Campos Disponibles

### 1. Ruta del archivo M3U

**Campo:** Texto libre
**Por defecto:** `dynamic_channels.m3u`
**Descripción:** Nombre del archivo M3U que se generará.

**Ejemplos:**
- `channels.m3u`
- `playlist.m3u`
- `streams.m3u`
- `tv_channels.m3u`
- `videos` (sin extensión)
- `canales` (sin extensión)

**Nota importante:** Puedes usar el nombre **con o sin** la extensión `.m3u`. El sistema funciona en ambos casos:
- Si pones `videos`, la URL será `http://IP/videos` (y descargará como `videos.m3u`)
- Si pones `videos.m3u`, la URL será `http://IP/videos.m3u`

### 2. URL de Acceso

**Generada automáticamente**
**Descripción:** Muestra la URL completa desde donde se puede acceder al M3U.

**Formato:** `http://IP-DEL-SERVIDOR/ruta-archivo.m3u`

**Ejemplo:**
- Si tu servidor está en `192.168.1.40` y configuraste `videos`
- URL: `http://192.168.1.40/videos`

**Nota:** La URL usa automáticamente la IP/dominio desde donde accedes a la interfaz

## Casos de Uso

### Caso 1: Cambiar solo el nombre del archivo (con extensión)

**Configuración:**
- Ruta del archivo M3U: `channels.m3u`
- Base personalizada: *(vacío)*

**Resultado:**
- URL antigua: `http://172.16.1.40/dynamic_channels.m3u`
- URL nueva: `http://172.16.1.40/channels.m3u`

### Caso 1b: Cambiar solo el nombre del archivo (sin extensión)

**Configuración:**
- Ruta del archivo M3U: `videos`
- Base personalizada: *(vacío)*

**Resultado:**
- URL antigua: `http://172.16.1.40/dynamic_channels.m3u`
- URL nueva: `http://172.16.1.40/videos`
- Descarga como: `videos.m3u`

### Caso 2: Cambiar solo el nombre (sin extensión)

**Configuración:**
- Ruta del archivo M3U: `videos`

**Resultado:**
- URL antigua: `http://192.168.1.40/dynamic_channels.m3u`
- URL nueva: `http://192.168.1.40/videos`
- Archivo descargado: `videos.m3u`

## Interfaz de Usuario

La interfaz muestra:
1. **Campo de texto para ruta del archivo** con validación
2. **Campo de texto para base personalizada** (opcional)
3. **Vista previa en tiempo real** de la URL resultante
4. **Botón "Guardar configuración M3U"**
5. **Mensaje de confirmación** con la nueva URL después de guardar

## API

### Obtener configuración actual

```bash
GET /api/config/m3u

Response:
{
  "success": true,
  "config": {
    "url_path": "dynamic_channels.m3u",
    "custom_base": null
  }
}
```

### Actualizar configuración

```bash
POST /api/config/m3u
Content-Type: application/json

{
  "url_path": "channels.m3u",
  "custom_base": "192.168.1.40"
}

Response:
{
  "success": true,
  "message": "Configuración de M3U actualizada correctamente",
  "example_url": "http://192.168.1.40/channels.m3u",
  "config": {
    "url_path": "channels.m3u",
    "custom_base": "192.168.1.40"
  }
}
```

## Retrocompatibilidad

La URL por defecto `http://IP/dynamic_channels.m3u` seguirá funcionando incluso si cambias la configuración, para no romper integraciones existentes.

## Almacenamiento

La configuración se guarda en: `~/.signally_config.json`

```json
{
  "auto_start": false,
  "configuracion_inicial": false,
  "m3u_url_path": "channels.m3u",
  "m3u_custom_base": "192.168.1.40"
}
```

## Validaciones

- El campo "Ruta del archivo M3U" no puede estar vacío
- Los protocolos (`http://`, `https://`) se eliminan automáticamente de la base
- Los slashes finales se eliminan automáticamente
- Los slashes iniciales en la ruta se eliminan automáticamente

## Características Técnicas

### Backend (ConfigManager)

- **Método:** `get_m3u_config()` - Obtiene configuración actual
- **Método:** `set_m3u_config(url_path, custom_base)` - Actualiza configuración
- **Método:** `build_m3u_url(request_host)` - Construye URL completa

### Frontend (conf.html)

- **Función:** `loadM3UConfig()` - Carga configuración al iniciar
- **Función:** `saveM3UConfig()` - Guarda configuración
- **Función:** `updateM3UCurrentUrl()` - Actualiza preview en tiempo real

### Rutas Flask

- `/dynamic_channels.m3u` - Ruta por defecto (retrocompatibilidad)
- `/<nombre>.m3u` - Ruta dinámica según configuración
