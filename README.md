# Monitorización infantil

Consulta la [guía de comandos para PowerShell](COMANDOS.md).
Los defectos, hallazgos de seguridad y mejoras se siguen en el [backlog técnico](BACKLOG.md).

Captura, visión y lógica temporal comparten el entorno Python `.venv` de la raíz.
En PyCharm, abre la raíz del proyecto y selecciona `.venv\Scripts\python.exe`
como intérprete.

Desde la raíz, instala las dependencias del prototipo en PowerShell:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Si el entorno ya existe, ejecuta solo la segunda línea. Las versiones de
PyTorch y torchvision corresponden a la instalación CUDA 12.8 del prototipo.

Para abrir la vista de cámara desde la raíz:

```powershell
.\.venv\Scripts\python.exe .\capture\scripts\preview_rtsp.py
```

La conexión se configura en `capture/.env`. Consulta [captura](capture/README.md),
[visión](ai/vision/README.md) y [motor temporal](ai/temporal/README.md) para
ejecutar sus pruebas y demostraciones.
