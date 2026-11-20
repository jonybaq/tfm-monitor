# Comandos del proyecto en Windows

Abre PowerShell en la raíz del proyecto, donde está `requirements.txt`.

## 1. Crear el entorno virtual

Ejecuta este comando una vez, o cuando necesites recrear el entorno:

```powershell
py -3.14 -m venv .venv
```

Si PowerShell no reconoce `py`, usa la ruta del ejecutable de Python 3.14
seguida de `-m venv .venv`.

## 2. Instalar las dependencias

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

La instalación incluye OpenCV, Ultralytics y PyTorch con CUDA 12.8.

## 3. Activar el entorno (opcional)

```powershell
.\.venv\Scripts\Activate.ps1
python --version
```

Para salir del entorno activado, ejecuta `deactivate`. Si PowerShell bloquea
`Activate.ps1`, puedes usar directamente los comandos con `python.exe` de esta
guía. En PyCharm, selecciona `.venv\Scripts\python.exe` como intérprete.

## 4. Abrir la cámara

Configura primero la conexión local en `capture/.env`. Desde la raíz:

```powershell
.\.venv\Scripts\python.exe .\capture\scripts\preview_rtsp.py
```

Pulsa `q` en la ventana para cerrar.

## 5. Probar YOLO y el motor temporal

Desde la raíz, ejecuta los siguientes bloques por separado. La demo con
celular y control remoto usa la cámara. La demo de consola usa señales simuladas.

```powershell
Push-Location ai\vision
..\..\.venv\Scripts\python.exe -m scripts.phone_persistence_demo
Pop-Location
```

```powershell
Push-Location ai\temporal
..\..\.venv\Scripts\python.exe -m scripts.demo
Pop-Location
```

Para comprobar si PyTorch detecta CUDA, desde la raíz ejecuta:

```powershell
.\.venv\Scripts\python.exe -c "import torch; print(torch.cuda.is_available())"
```

## 6. Levantar TaskView y su MCP local

Con Docker Desktop iniciado, ejecuta estos comandos desde cualquier carpeta de
PowerShell:

```powershell
docker compose -f "C:\Users\jony_\taskview\docker-compose.yml" up -d
docker compose -f "C:\Users\jony_\taskview\docker-compose.yml" ps
```

Abre [TaskView](http://localhost:8888) y entra en **TFM-MONITOR**. La API está
disponible en `http://localhost:1725`.

El MCP corre en un contenedor aparte. Si ya existe y está detenido, levántalo
después de TaskView:

```powershell
docker start taskview-mcp-local
Invoke-RestMethod http://127.0.0.1:3100/health
```

La dirección del MCP es `http://127.0.0.1:3100/mcp`.

## 7. Enviar vídeo y audio de la Tapo a Azure

Para la HU-02 se usará **`ffmpeg.exe` instalado en Windows**. El programa Python
lo ejecutará mediante `subprocess`, que viene con Python. El entorno
`.venv` no necesita instalar `ffmpeg-python`, PyAV ni otro paquete para este envío.

Si FFmpeg ya está instalado, comprueba que PowerShell lo encuentra con
`ffmpeg -version`. En otro equipo Windows, instálalo con este comando
y abre una nueva ventana de PowerShell para comprobar la versión:

```powershell
winget install --id Gyan.FFmpeg --exact
ffmpeg -version
```

Desde la raíz del proyecto, con FFmpeg disponible en PowerShell y
`tapo-media` en ejecución, pega este bloque. Introduce la IP pública actual de
`tapo-media` y la frase SRT de publicación configurada en Azure. La URL RTSP
se obtiene de `capture/.env`.

```powershell
Push-Location .\capture
try {
    $tapoUrl = & '..\.venv\Scripts\python.exe' -B -c 'from rtsp.config import RtspConfig; print(RtspConfig.from_environment().url)'
    if ($LASTEXITCODE -ne 0 -or -not $tapoUrl) {
        throw 'Revisa la configuración RTSP de capture/.env.'
    }
} finally {
    Pop-Location
}

$azureIp = Read-Host 'IP publica de tapo-media'
$srtPassphrase = Read-Host 'Frase SRT de publicacion'
$srtDestination = "srt://${azureIp}:8890?mode=caller&streamid=publish:tapo&pkt_size=1316&pbkeylen=32&passphrase=$([Uri]::EscapeDataString($srtPassphrase))"

ffmpeg -hide_banner -loglevel warning -stats -rtsp_transport tcp -i $tapoUrl `
    -map 0:v:0 -map 0:a:0 -c:v copy `
    -bsf:v 'setts=pts=N/(30*TB):dts=N/(30*TB)' `
    -c:a libopus -ar 48000 -ac 1 -b:a 32k -f mpegts $srtDestination
```

Cuando suba el contador `frame=`, abre en Chrome
`http://IP_PUBLICA:8889/tapo/?muted=false&autoplay=false`, sustituye
`IP_PUBLICA` por la IP del contenedor y pulsa **Reproducir**. Pulsa
`Ctrl+C` en PowerShell para detener el envío.

En la prueba se vieron vídeo y audio con unos 2 segundos de retraso de
cámara a pantalla. El ajuste de marcas de tiempo supone una fuente a 30 FPS.
