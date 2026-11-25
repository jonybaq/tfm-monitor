# HU-04 · Controles de la Tapo C220

Lista L-04 · Sprint 2 · Investigación documental

## Resultado

El vídeo y el audio por RTSP ya se probaron en la Tapo del proyecto. El control
de la cámara será un módulo local independiente en `camera_control/`. FFmpeg
seguirá leyendo y enviando el directo desde `streaming/`.

| Control | Evidencia encontrada | Comprobación pendiente |
| --- | --- | --- |
| Giro e inclinación | TP-Link documenta PTZ mediante ONVIF Profile S en sus cámaras Tapo compatibles. | Probar las cuatro direcciones en nuestra C220 mientras FFmpeg transmite. |
| Regreso al encuadre | La integración comunitaria Tapo Control ofrece posiciones predefinidas. | Verificar qué opciones de guardado y recuperación expone nuestro firmware. |
| Día, noche y automático | La C220 incorpora visión nocturna IR. Tapo Control ofrece un selector de modo día/noche. | Consultar los modos disponibles, cambiar el modo y verificar el resultado en el directo. |
| Micrófono | La C220 tiene micrófono integrado. Tapo Control ofrece un interruptor de silencio del micrófono. | Verificar que se pueda desactivar y reactivar, y comprobar qué recibe el análisis de llanto. |

## Decisión para el desarrollo

1. **HU-12 · Encuadre.** Probar ONVIF primero y registrar la versión del
   firmware, la interfaz y el resultado. Al mover la cámara se deben revisar
   las zonas de supervisión si el encuadre cambia.
2. **HU-13 · Visión nocturna.** Evaluar PyTapo como alternativa comunitaria si
   el firmware no expone el control necesario por una interfaz documentada.
3. **HU-14 · Micrófono.** Aplicar la misma comprobación de compatibilidad.
   Silenciar el audio de origen afecta al detector de llanto. Silenciar el
   reproductor del celular solo afecta a la reproducción.
4. **HU-15 · Control remoto.** Definir autorización y entrega de órdenes. La
   propuesta es que el módulo local inicie la conexión al backend y conserve
   las credenciales de la cámara en la red local.

La compatibilidad de PyTapo depende del modelo y el firmware. Hay reportes
comunitarios de fallos de autenticación en algunas versiones de la C220.
En esta investigación no se instaló PyTapo ni se cambiaron ajustes de la
cámara. El movimiento, las posiciones, el modo nocturno y el micrófono
quedan pendientes de verificación física en sus respectivas historias.

## Fuentes

- [TP-Link Ecuador · RTSP, ONVIF y control PTZ](https://www.tp-link.com/ec/support/faq/2680/)
- [TP-Link · Ficha técnica de Tapo C220](https://static.tp-link.com/upload/product-overview/2025/202506/20250623/Tapo%20C220%201.0%261.6_Datasheet.pdf)
- [Tapo Control · Funciones de la integración comunitaria](https://github.com/JurajNyiri/HomeAssistant-Tapo-Control)
- [PyTapo · Biblioteca no oficial](https://github.com/JurajNyiri/pytapo)
- [PyTapo · Reporte de autenticación en C220](https://github.com/JurajNyiri/pytapo/issues/135)
