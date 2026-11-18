# CAP-06 · Revisión de OpenCV y FFmpeg

Revisión del 18 de noviembre de 2026 para la captura RTSP en Windows.

- Paquete instalado: `opencv-python 5.0.0.93`. OpenCV informa `5.0.0`.
- Backend: FFmpeg precompilado, con `libavcodec 61.19.100`,
  `libavformat 61.7.100`, `libavutil 59.39.100` y `libswscale 8.3.100`.
- Las numeraciones coinciden con las publicadas para FFmpeg 7.1.5.
  La información de compilación disponible deja pendiente confirmar la revisión
  exacta y los parches incorporados en el binario de Windows.
  [Versiones de FFmpeg](https://ffmpeg.org/download.html)

## Aplicabilidad al preview

RTSP pasa por `libavformat` y el vídeo se decodifica mediante `libavcodec`.
Estos componentes son relevantes para evaluar avisos relacionados con el flujo
de cámara. El listado oficial de FFmpeg recoge correcciones en la rama 7.1,
pero su presencia en este binario concreto queda sin confirmar.
[Avisos de FFmpeg](https://ffmpeg.org/security.html) ·
[Documentación RTSP](https://ffmpeg.org/ffmpeg-protocols.html#rtsp)

La página de seguridad de OpenCV no lista avisos publicados en el repositorio.
El informe público #1272 sobre `opencv-python 5.0.0.93` cita FFmpeg 8.1.1.
Esa versión difiere de la numeración observada en Windows, por lo que el
informe por sí solo no permite asignar esos hallazgos a esta instalación.
[Seguridad de OpenCV](https://github.com/opencv/opencv/security) ·
[Informe #1272](https://github.com/opencv/opencv-python/issues/1272)

Resultado: aplicabilidad de CVE al binario local indeterminada con la evidencia
disponible. Se mantienen las dependencias actuales para esta revisión. Si se
evalúa otro paquete, verificar su procedencia y los parches del backend antes
de probar apertura, lectura y reconexión con la Tapo.

## Comprobación reproducible

Desde la raíz, en PowerShell:

```powershell
.\.venv\Scripts\python.exe -B -c "import cv2, importlib.metadata as m; print(m.version('opencv-python')); print(cv2.getBuildInformation())" |
    Select-String '5\.0\.0|FFMPEG|avcodec|avformat|avutil|swscale'
```
