# Elección del emisor audiovisual para la Tapo C220

**HU-01 · Sprint 1 · 20 de noviembre de 2026**

Se elige **FFmpeg con SRT sobre UDP** para el prototipo. Es la configuración con vídeo y audio ya probada con MediaMTX en Azure y la que requiere menos configuración para el lanzador Python de la HU-02.

## Prueba realizada

La Tapo C220 entregó vídeo y audio por RTSP a FFmpeg en una laptop Windows. FFmpeg conservó el vídeo H.264, aplicó el ajuste de marcas de tiempo para 30 FPS y convirtió el audio a Opus. La laptop publicó ambas pistas por SRT en MediaMTX dentro de Azure Container Instances. MediaMTX entregó el directo a Chrome por WebRTC. Los registros de MediaMTX confirmaron H.264 y Opus tanto en la entrada SRT como en la sesión WebRTC.

El operador observó aproximadamente **2 segundos de cámara a pantalla** con vídeo y audio. Es una observación de esa prueba y cubre la ruta completa. Las primeras variantes presentaron cortes y también se constató que MediaMTX omitía el audio AAC en la salida WebRTC. Con Opus se verificó la reproducción de ambas pistas. La prueba local con MediaMTX leyendo RTSP directamente se percibió como instantánea. Su recorrido es diferente del envío local que deberá validar la HU-02.

## Alternativas revisadas

| Programa | Configuración y automatización | Evidencia |
| --- | --- | --- |
| FFmpeg | Un ejecutable en Windows. Python puede pasarle el origen RTSP y el destino SRT mediante `subprocess`. | Envío con H.264 y Opus validado en Azure. |
| GStreamer | Configuración por componentes de RTSP, vídeo, audio, empaquetado y SRT. Permite ajustar colas e integrarse mediante su API de Python. | Compatibilidad documentada. Sin mediciones con esta cámara y Azure. |
| OBS Studio | Requiere configurar una fuente y un perfil. Puede iniciar la emisión desde la línea de comandos o controlarse mediante WebSocket. Su flujo habitual vuelve a codificar el vídeo. | Publicación SRT y WHIP documentada. Sin mediciones con esta cámara y Azure. |

SRT permite cifrar la publicación y recuperar paquetes perdidos dentro de su margen de entrega. MPEG-TS sobre UDP directo se consideró como referencia local. WHIP es una alternativa de publicación WebRTC y la instalación de FFmpeg incluye su multiplexor. Ambas opciones quedaron en revisión documental y sin comparación de rendimiento en Azure. TP-Link documenta RTSP y ONVIF para la C220. No se encontró un ajuste oficial para publicar directamente en un destino SRT o WHIP propio.

## Decisión para la HU-02

El lanzador usará `ffmpeg.exe` instalado en Windows con WinGet. Lo ejecutará mediante `subprocess`, parte de la biblioteca estándar de Python. El envío no requiere una librería adicional en `.venv`. El modo local o Azure se seleccionará por configuración y las credenciales se mantendrán fuera del repositorio.

La elección se basa en la prueba operativa y la facilidad de integración. Sigue haciendo falta un emisor encendido en la red de la cámara mientras se publica. La HU-02 deberá validar conexión inicial, espera de cámara o receptor y recuperación ante cortes en los dos modos. La HU-04 cubre las pruebas de seguridad de publicación.

## Fuentes

- [Ficha técnica de la Tapo C220](https://static.tp-link.com/upload/product-overview/2025/202509/20250925/Tapo%20C220%202.0%262.6_Datasheet.pdf)
- [Publicación con FFmpeg en MediaMTX](https://mediamtx.org/docs/publish/ffmpeg)
- [SRT en MediaMTX](https://mediamtx.org/docs/publish/srt-clients)
- [MPEG-TS sobre UDP en MediaMTX](https://mediamtx.org/docs/publish/mpeg-ts)
- [Publicación con GStreamer en MediaMTX](https://mediamtx.org/docs/publish/gstreamer)
- [API y herramienta de línea de comandos de GStreamer](https://gstreamer.freedesktop.org/documentation/tools/gst-launch.html)
- [Emisión SRT en OBS](https://obsproject.com/kb/srt-protocol-streaming-guide)
- [Emisión WHIP en OBS](https://obsproject.com/kb/whip-streaming-guide)
- [Parámetros de inicio de OBS](https://obsproject.com/kb/launch-parameters/)
- [Reproducción WebRTC y formatos compatibles en MediaMTX](https://mediamtx.org/docs/read/webrtc)
