# Captura RTSP

Este subproyecto implementa M1: adquisición de vídeo RTSP en un hilo
independiente y conservación exclusiva del frame más reciente. No ejecuta
inferencia ni analiza audio.

## Entorno virtual y dependencias

Usa el entorno compartido de la raíz descrito en el [README general](../README.md).
La vista de diagnóstico utiliza OpenCV con interfaz gráfica.

Desde `capture/`, comprueba la instalación:

```powershell
..\.venv\Scripts\python.exe -c "import cv2; print(cv2.__version__)"
```

## Configuración local

La forma más sencilla, especialmente desde VS Code, es crear el archivo local
`capture/.env` a partir de `capture/.env.example` y completar sus valores. Ese
archivo está ignorado por Git: no lo subas ni lo compartas.

Como alternativa, define las variables en la misma sesión de PowerShell desde
la que arrancarás el programa:

```powershell
$env:RTSP_USERNAME = "tu_usuario"
$env:RTSP_PASSWORD = "tu_contrasena"
$env:RTSP_HOST = "ip_local_de_la_camara"
$env:RTSP_PORT = "554"
$env:RTSP_STREAM_PATH = "stream1"
```

`stream2` puede probarse cambiando solo `RTSP_STREAM_PATH`. La resolución la
emite la cámara; no se fuerza desde OpenCV.

## Diagnóstico manual

Desde la carpeta `capture/`, con el entorno virtual ya configurado:

```powershell
..\.venv\Scripts\python.exe -m scripts.preview_rtsp
```

Pulsa `q` o cierra la ventana con la X para terminar. El comando no muestra ni
registra la URL ni las credenciales RTSP. Al cerrar, registra las métricas de
captura disponibles. La ventana muestra FPS de captura, edad del frame,
conexión, errores y reconexiones. Las mismas métricas se escriben en el log de
PyCharm cada cinco segundos.

## Pruebas unitarias

```powershell
..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas unitarias no necesitan cámara, GPU ni credenciales.
