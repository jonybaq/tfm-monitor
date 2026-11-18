# AGENTS.md

## Project Overview

Este repositorio contiene el desarrollo del TFM provisionalmente
titulado **"Sistema de monitorización infantil para la detección de
situaciones de riesgo mediante análisis audiovisual temporal"**.

Es un TFM de Máster en Inteligencia Artificial de **Tipo 2 ---
Desarrollo**. La contribución principal debe ser una solución software
funcional, demostrable y evaluable. La IA forma parte del sistema, pero
el proyecto no debe convertirse en una simple comparación de modelos.

El sistema supervisará mediante vídeo y audio a un niño mientras se
encuentra en la cuna y utilizará IA, análisis espacial y análisis
temporal para detectar situaciones relevantes, registrar eventos y
generar alertas al cuidador.

## Principios del proyecto

-   Priorizar una solución viable y demostrable desde casa.
-   Mantener desacopladas adquisición, IA visual, IA acústica, motor
    contextual-temporal, backend y aplicación móvil.
-   No interpretar automáticamente una detección aislada como una
    situación de riesgo.
-   La decisión de crear eventos y alertas corresponde al motor
    contextual-temporal.
-   No introducir tecnologías sin justificar qué problema resuelven.
-   Evitar sobrearquitectura.
-   No convertir el TFM en una comparación de modelos.
-   No asumir decisiones técnicas marcadas como "por definir".

## Arquitectura objetivo

``` text
TP-Link Tapo C220
       │ RTSP vídeo + audio
       ▼
Capa de adquisición
   ┌───┴────────────┐
   ▼                ▼
Pipeline visual   Pipeline audio
   │                │
YOLO / pose /     detector de llanto
segmentación /
tracking
   └───────┬────────┘
           ▼
Motor contextual-temporal
           │
Backend / API / BD
   ├──────────────┐
   ▼              ▼
Eventos/alertas  App móvil + vídeo remoto
```

WebRTC es candidato para retransmisión remota, pero no una decisión
cerrada.

## Tecnología confirmada

-   Python.
-   PyTorch.
-   OpenCV.
-   Ultralytics.
-   Familia YOLO para detección visual.
-   TP-Link Tapo C220.
-   RTSP.
-   Windows 11.
-   NVIDIA GeForce RTX 5070 Laptop GPU, 8 GB VRAM.

### Modelo actual

**YOLO11n** se utiliza como modelo de prototipo para validar RTSP, CUDA,
inferencia, latencia, FPS y el pipeline en tiempo real.

YOLO11n **no es todavía el modelo final del TFM**. La familia YOLO sí
está prevista; la variante definitiva deberá justificarse
posteriormente.

## Tecnologías candidatas / por definir

-   PyAV para demultiplexado audiovisual.
-   React Native + Expo para aplicación móvil.
-   WebRTC para vídeo remoto.
-   Framework backend.
-   Base de datos.
-   Tracking.
-   Modelo de pose.
-   Modelo de segmentación.
-   Modelo acústico de llanto.
-   Push notifications.
-   Autenticación.
-   Infraestructura cloud.

No fijar versiones arbitrarias.

### Nota de diseño: tracking multiobjeto

Ultralytics puede aportar identificadores temporales por objeto al procesar
frames consecutivos con `model.track(..., persist=True)`. Esos identificadores
los mantiene un tracker; una detección aislada no identifica persistentemente un
objeto. Esta capacidad será candidata para distinguir varios objetos y sus
relaciones individuales con el rostro. El tracker concreto, sus parámetros y
su validación siguen por definir.

## Situaciones a interpretar

1.  Niño boca abajo.
2.  Rostro cubierto u ocluido.
3.  Objeto próximo al rostro.
4.  Niño en una zona crítica de la cuna.
5.  Intento de salir de la cuna.
6.  Ausencia o salida de la zona de supervisión.
7.  Llanto.

Estas situaciones no equivalen automáticamente a una emergencia.

## Motor contextual-temporal

Debe transformar detecciones individuales en estados y eventos:

``` text
detección → estado → relación espacial → persistencia temporal
→ evolución → evento → nivel de alerta
```

Debe poder analizar duración, persistencia, proximidad, solapamiento,
regiones de interés, zonas críticas, relaciones niño-rostro-objeto,
movimiento, evolución y combinación de señales visuales/acústicas.

Los umbrales temporales definitivos están por definir. No inventarlos.

## Niveles conceptuales

-   Nivel 1: informativo / registro.
-   Nivel 2: atención.
-   Nivel 3: prioridad elevada.

Reglas y umbrales definitivos: por validar.

## Reglas RTSP

-   Nunca hardcodear IP, usuario o contraseña.
-   Usar configuración externa o variables de entorno.
-   Desacoplar captura e inferencia.
-   Mantener preferentemente el frame más reciente.
-   Evitar colas crecientes de frames antiguos.
-   Permitir descarte de frames para mantener baja latencia.
-   Diseñar para reconexión y manejo de errores.
-   Evaluar `stream1` y `stream2`.
-   No asumir que `CAP_PROP_FRAME_WIDTH/HEIGHT` modifica la resolución
    emitida por la cámara RTSP.

## Reglas de IA

Antes de añadir un modelo nuevo:

1.  Explicar qué problema resuelve.
2.  Justificar por qué el componente existente no basta.
3.  Considerar precisión.
4.  Considerar latencia.
5.  Considerar hardware.
6.  Definir cómo se validará.

No usar YOLO para todas las tareas por defecto. Evaluar detección, pose,
segmentación, tracking, clasificación y reglas geométricas según el
problema.

No entrenar modelos fundacionales desde cero.

## Audio

Objetivo inicial:

``` text
audio → modelo acústico → llanto / no llanto
```

No ampliar a hambre, dolor, sueño, cansancio o enfermedad sin revisar
formalmente el alcance.

Mute en la futura app solo silencia la reproducción; no detiene el
análisis acústico.

## Rendimiento

Distinguir:

-   inference latency;
-   frame age;
-   processing FPS;
-   end-to-end latency.

No interpretar `model.predict()` como latencia total.

No activar FP16, INT8, INT4 o cuantización sin medir precisión y
rendimiento.

## Seguridad

Nunca almacenar en Git:

-   credenciales RTSP;
-   contraseñas;
-   `.env`;
-   tokens;
-   API keys;
-   secretos JWT;
-   claves privadas;
-   credenciales cloud.

Debe existir `.env.example` sin valores reales y `.env` debe estar en
`.gitignore`.

No exponer RTSP directamente a Internet ni entregar credenciales de
cámara a la app móvil.

## Datos y privacidad

No almacenar en el repositorio vídeos/fotos personales, datos
identificables ni datasets privados.

Antes de una recogida formal de imágenes o vídeos identificables de
menores, confirmar los requisitos éticos y académicos aplicables.
Mientras esté pendiente, priorizar muñecos/maniquíes, datasets públicos,
datos sintéticos o escenas sin información personal cuando sea viable.

## Convenciones Python

-   PEP 8.
-   Variables/funciones: `snake_case`.
-   Clases: `PascalCase`.
-   Constantes: `UPPER_SNAKE_CASE`.
-   Type hints cuando aporten claridad.
-   Evitar funciones monolíticas.
-   Logging en producción.
-   Evitar `except:` genérico.
-   Separar configuración y código.
-   No ejecutar inferencia pesada en el hilo de UI.
-   No bloquear captura mientras se ejecuta inferencia.

## Estructura prevista

``` text
project/
├── AGENTS.md
├── PRD.md
├── README.md
├── .env.example
├── .gitignore
├── ai/
│   ├── vision/
│   ├── audio/
│   └── temporal/
├── capture/
│   ├── rtsp/
│   └── audiovisual/
├── backend/
├── mobile/
├── configs/
├── scripts/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── end_to_end/
└── docs/
```

No crear capas/carpetas vacías solo para seguir el esquema.

## Git

Convención inicial:

-   `main`
-   `develop`
-   `feature/<descripcion>`
-   `fix/<descripcion>`
-   `experiment/<descripcion>`

Commits pequeños y descriptivos. No incluir secretos ni datos
personales. Separar experimentos de funcionalidad estable. La política
merge/rebase definitiva se decidirá cuando exista repositorio remoto.

## Testing

### Unitarios

Toda corrección de una tarea debe quedar cubierta por pruebas unitarias.
Adapta las pruebas existentes si cambia el comportamiento esperado y añade
una prueba de regresión si el caso carece de cobertura. Ejecuta la suite del
componente y registra el resultado en la tarea, junto a su ID, antes de
moverla a Done en TaskView. Realiza también las comprobaciones adicionales
que exija su criterio de cierre.

Priorizar reglas temporales, duración, persistencia, zonas, distancias,
solapamientos, niveles de alerta y transformación estado→evento.

### Integración

Validar RTSP→captura, frame→IA→detección, audio→IA, detecciones→motor
temporal→evento, evento→backend→BD y backend→app.

### End-to-end

``` text
Entrada audiovisual → IA → interpretación contextual/temporal
→ evento → persistencia → alerta → aplicación móvil
```

## Estado técnico actual

Ya se ha probado:

``` text
Tapo C220 → RTSP → Python → OpenCV → YOLO11n
→ RTX 5070 → detecciones en pantalla
```

El primer prototipo acumulaba retraso con captura e inferencia
secuenciales. Se mejoró desacoplando la captura mediante un hilo que
conserva el frame más reciente.

También se ha trabajado con CUDA, warm-up, `imgsz=640`, medición de
inferencia/FPS, reducción de buffering y PyAV como candidato para
audio+vídeo.

## Decisiones pendientes

No asumir todavía:

-   variante YOLO definitiva;
-   pose;
-   segmentación;
-   tracking;
-   modelo acústico;
-   reglas y umbrales temporales;
-   backend;
-   base de datos;
-   autenticación;
-   framework móvil definitivo;
-   streaming remoto;
-   push provider;
-   cloud;
-   estrategia de deploy.

## Reglas específicas para Codex

Antes de modificar código:

1.  Leer `PRD.md`.
2.  Inspeccionar la implementación existente.
3.  No duplicar componentes.
4.  Mantener el alcance del ticket.
5.  No implementar funcionalidades futuras "por si acaso".
6.  Añadir tests cuando corresponda.
7.  Explicar cambios arquitectónicos importantes.
8.  No introducir dependencias innecesarias.
9.  No inventar decisiones académicas.
10. No modificar silenciosamente requisitos.

## Prioridad actual

Primer milestone:

``` text
Tapo C220 → RTSP → captura estable del frame reciente
→ YOLO → métricas → tests
```

No comenzar por cloud, backend complejo o app completa.
