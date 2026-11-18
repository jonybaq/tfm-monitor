# Pipeline visual — M2

Este subproyecto recibe imágenes y devuelve detecciones estructuradas. No abre
RTSP, no decide alertas y no contiene reglas temporales.

El modelo inicial es `yolo11n.pt`, únicamente como baseline validado en M0. La
variante final se decidirá tras medir precisión, recall/F1, latencia, FPS y VRAM.

## Tracking multiobjeto — decisión pendiente

Ultralytics dispone de modo de tracking para secuencias de frames y puede
entregar un identificador temporal (`track_id`) distinto por objeto usando
`model.track(..., persist=True)`. El ID lo produce un tracker entre frames, no
la detección YOLO aislada. Esto será necesario para analizar por separado varios
objetos cerca del rostro; todavía no se ha seleccionado ni validado un tracker.

Cuando se evalúe, se compararán precisión de identidad, pérdidas/intercambios de
ID, latencia y coste de VRAM en la escena estática de la cuna.

## Pruebas

Usa el entorno compartido descrito en el [README general](../../README.md).

Desde `ai/vision/`:

```powershell
..\..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Prueba visual manual

Desde `ai/vision/`, ejecuta:

```powershell
..\..\.venv\Scripts\python.exe -m scripts.preview_image
```

Por defecto descarga una imagen pública de prueba. Para usar otra imagen local
no personal: `--source ruta\\a\\imagen.jpg`.

## Demo de persistencia de celular

`scripts/phone_persistence_demo.py` usa cámara y YOLO, y muestra un mensaje si
la etiqueta `cell phone` o `remote` se mantiene cinco segundos seguidos. Ambas
clases tienen contadores independientes. Es una demo M3, no una alerta real ni
identificación individual de objetos.

## Prueba en vivo con la cámara

La herramienta de integración usa `capture/.env` y el componente de captura
existente; no duplica las credenciales ni la conexión RTSP. Desde `ai/vision/`:

```powershell
..\..\.venv\Scripts\python.exe scripts\preview_live.py
```

Pulsa `q` o cierra la ventana para terminar.
