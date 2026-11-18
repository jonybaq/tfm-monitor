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
