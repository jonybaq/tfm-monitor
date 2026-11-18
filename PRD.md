# PRD.md

# Sistema de monitorización infantil para la detección de situaciones de riesgo mediante análisis audiovisual temporal

## 1. Product Overview

Sistema software de monitorización infantil que analizará continuamente
vídeo y audio procedentes de una cámara IP situada en la zona de la
cuna.

Utilizará inteligencia artificial junto con análisis espacial y temporal
para identificar situaciones relevantes, mantener estados, registrar
eventos y generar alertas cuando una situación persista o evolucione.

El usuario principal será el cuidador, que podrá supervisar remotamente
al niño mediante una aplicación móvil, consultar eventos y recibir
alertas.

## 2. Contexto académico

TFM de Máster en Inteligencia Artificial, **Tipo 2 --- Desarrollo**.

La contribución principal debe ser una solución software funcional,
demostrable y evaluable con IA integrada de forma relevante. Una
comparación de modelos puede utilizarse para tomar decisiones técnicas,
pero no constituye la contribución principal.

## 3. Problema

Una detección individual de presencia, postura, objetos, movimiento o
llanto no necesariamente representa una situación que requiera
intervención.

El sistema deberá interpretar:

``` text
qué ocurre + dónde ocurre + durante cuánto tiempo + cómo evoluciona
```

para transformar detecciones en eventos útiles para el cuidador.

## 4. Hipótesis de aporte

Desarrollar una capa contextual espacio-temporal capaz de combinar
información visual y acústica para determinar cuándo una situación debe
registrarse, mantenerse como estado, generar atención o escalar a una
alerta.

La novedad definitiva deberá validarse mediante estado del arte
científico y análisis de soluciones existentes.

## 5. Usuario objetivo

### Cuidador

Necesita:

-   visualizar al niño;
-   conocer su estado;
-   recibir alertas relevantes;
-   consultar eventos anteriores;
-   acceder al vídeo cuando ocurre un evento;
-   minimizar falsas alarmas.

El sistema no se plantea inicialmente como dispositivo médico.

## 6. Objetivo general

Desarrollar un sistema inteligente de monitorización infantil basado en
análisis audiovisual que permita detectar, interpretar y registrar
situaciones potencialmente relevantes o de riesgo durante la permanencia
del niño en la cuna, utilizando información visual, acústica, espacial y
temporal para generar alertas graduadas al cuidador.

## 7. Objetivos específicos

1.  Implementar adquisición continua de vídeo y audio desde una cámara
    IP.
2.  Desarrollar visión artificial para detectar al niño, objetos
    relevantes y relaciones espaciales.
3.  Incorporar pose, segmentación y tracking cuando sean necesarios.
4.  Implementar detección acústica de llanto mediante un modelo
    preentrenado.
5.  Desarrollar un motor contextual-temporal.
6.  Implementar backend y persistencia para estados, eventos y alertas.
7.  Desarrollar una aplicación móvil para supervisión remota.
8.  Evaluar precisión, falsas alarmas, latencia y funcionamiento
    end-to-end.

## 8. Situaciones contempladas

-   niño boca abajo;
-   rostro cubierto;
-   objeto próximo al rostro;
-   niño en zona crítica;
-   intento de salida;
-   ausencia/salida de zona de supervisión;
-   llanto.

# 9. Requisitos funcionales

## FR-01 --- Adquisición RTSP

El sistema deberá adquirir vídeo desde una TP-Link Tapo C220 mediante
RTSP.

### Acceptance Criteria

-   Credenciales no hardcodeadas.
-   Configuración desde el entorno.
-   Inicio/parada controlados.
-   Detección de errores de lectura.
-   Diseño compatible con reconexión.
-   Acceso al frame más reciente.
-   Inferencia desacoplada de captura.

## FR-02 --- Inferencia visual

Pipeline visual basado inicialmente en modelos de la familia YOLO.

YOLO11n es modelo de prototipo, no selección definitiva.

### Acceptance Criteria

-   Recibe frames.
-   Devuelve resultados estructurados.
-   Incluye timestamps.
-   Expone clase/confianza/geometría cuando corresponda.
-   Puede usar CUDA.
-   No está acoplado a RTSP.
-   El modelo puede sustituirse sin reescribir captura.

## FR-03 --- Estado boca abajo

Identificar cuándo la postura observada es compatible con el estado
definido como boca abajo.

### Acceptance Criteria

-   Resultado representado como estado.
-   Timestamp disponible.
-   Duración acumulable.
-   Un frame aislado no genera automáticamente alerta crítica.
-   Técnica evaluable con datos de prueba.

## FR-04 --- Rostro cubierto

Identificar posibles situaciones de cobertura/oclusión facial.

### Acceptance Criteria

-   Representación de región facial o evidencia equivalente.
-   Diferenciar detección puntual y situación persistente.
-   Resultado consumible por motor temporal.
-   Evaluación mediante escenarios etiquetados.

## FR-05 --- Objeto próximo al rostro

Analizar relaciones espaciales entre objetos relevantes y región facial.

### Acceptance Criteria

-   Objeto relevante localizado.
-   Referencia espacial del rostro disponible.
-   Relación geométrica calculada.
-   Resultado representado como estado.
-   Persistencia evaluada fuera del detector.
-   No fijar todavía umbrales definitivos en píxeles.

## FR-06 --- Zona crítica

Permitir definir regiones relevantes dentro de la escena.

### Acceptance Criteria

-   Una o varias regiones de interés configurables.
-   Posición del niño relacionable con regiones.
-   Resultado mantenible temporalmente.
-   Regiones desacopladas del modelo de IA.

## FR-07 --- Intento de salida

Identificar patrones compatibles con intento de salir de la cuna.

Puede requerir postura, posición, movimiento, tracking, zonas y
secuencia temporal.

### Acceptance Criteria

-   No depender exclusivamente de una detección puntual.
-   Utilizar evidencia temporal cuando sea necesaria.
-   Generar estado/evento estructurado.
-   Validable mediante secuencias de vídeo.

### Nota de diseño: tracking multiobjeto

Para situaciones que dependan de varios objetos o de su evolución, el sistema
podrá requerir tracking. Ultralytics ofrece tracking con IDs temporales al
procesar frames consecutivos; el ID no procede de una detección aislada, sino
del tracker. Esta capacidad permitirá, si se valida, medir por separado las
relaciones objeto–rostro de varios objetos. La elección del tracker, sus
parámetros, precisión de identidad, intercambios/pérdidas de ID, latencia y
coste de VRAM permanecen pendientes de evaluación.

## FR-08 --- Ausencia

Identificar cuándo el niño deja la zona configurada de supervisión.

### Acceptance Criteria

-   Zona de supervisión definida.
-   Determinación presencia/ausencia.
-   Una pérdida de detección de un frame no equivale automáticamente a
    ausencia.
-   Tolerancia temporal configurable.

## FR-09 --- Detección de llanto

Analizar audio para estimar llanto/no llanto.

### Acceptance Criteria

-   Audio procesado independientemente de visualización.
-   Resultado con timestamp.
-   Integrable con estados visuales.
-   Mute en app no detiene IA.
-   Rendimiento evaluable con precision/recall/F1 o equivalente.

## FR-10 --- Motor contextual-temporal

Mantener y actualizar estados en el tiempo considerando inicio,
duración, persistencia, finalización, evolución, relaciones espaciales y
combinación de señales.

### Acceptance Criteria

-   Representar explícitamente detección→estado→persistencia→evento.
-   Estados independientes de UI.
-   Reglas testeables sin ejecutar YOLO.
-   Umbrales configurables y no inventados.

## FR-11 --- Niveles de alerta

Permitir diferentes niveles de relevancia:

-   Nivel 1: informativo/registro.
-   Nivel 2: atención.
-   Nivel 3: prioridad elevada.

### Acceptance Criteria

-   Cada evento tiene nivel.
-   El nivel puede cambiar con el tiempo.
-   El motor temporal determina escalada.
-   Umbrales configurables.
-   La UI no contiene la lógica principal de decisión.

## FR-12 --- Historial de eventos

Persistir eventos relevantes.

Campos candidatos:

``` text
id
tipo
timestamp_inicio
timestamp_fin
duracion
nivel
confianza/evidencia
estado
metadata
```

### Acceptance Criteria

-   Eventos persistibles.
-   Recuperación cronológica.
-   Consulta desde app.
-   Metadata extensible.

## FR-13 --- Vídeo en vivo

La app deberá permitir visualizar remotamente el stream audiovisual.

### Acceptance Criteria

-   No requerir misma Wi-Fi que la cámara.
-   No entregar credenciales RTSP a la app.
-   Control de audio/mute.
-   Mute afecta solo reproducción.
-   Análisis acústico continúa.

WebRTC es candidato; decisión definitiva pendiente.

## FR-14 --- Notificaciones

Notificar eventos relevantes al cuidador.

### Acceptance Criteria

-   Eventos configurados pueden generar notificación.
-   Notificación identifica tipo de evento.
-   Representa prioridad.
-   Al abrirla, la app puede mostrar información relacionada.
-   La decisión de alertar no reside exclusivamente en el teléfono.

# 10. Requisitos no funcionales

## NFR-01 --- Baja latencia

Priorizar información reciente y evitar acumulación indefinida de
frames.

## NFR-02 --- Modularidad

Desacoplar captura, IA visual, IA acústica, motor temporal, backend,
persistencia y app.

## NFR-03 --- Seguridad

No almacenar secretos en Git, no exponer RTSP directamente a Internet y
no entregar credenciales de cámara al cliente móvil.

## NFR-04 --- Privacidad

Minimizar almacenamiento audiovisual innecesario y no incluir datos
personales en repositorios.

## NFR-05 --- Configurabilidad

Cámara, modelo, confianza, regiones y umbrales deben poder evolucionar
sin grandes cambios de código.

## NFR-06 --- Testabilidad

La lógica temporal debe poder probarse sin cámara física, GPU ni app
móvil.

## NFR-07 --- Observabilidad

Medir inferencia, FPS, errores de captura, estado de conexión y eventos
generados.

# 11. Métricas previstas

### IA visual

-   precision;
-   recall;
-   F1;
-   mAP cuando corresponda.

### Eventos

-   event precision;
-   event recall;
-   F1;
-   falsas alarmas.

### Audio

-   precision;
-   recall;
-   F1.

### Sistema

-   inference latency;
-   processing FPS;
-   frame age;
-   end-to-end latency;
-   tiempo hasta alerta.

# 12. Datos

Fuentes posibles:

-   datasets públicos;
-   escenas controladas;
-   datos sintéticos;
-   vídeos/fotos propios cuando su uso esté autorizado;
-   muñecos/maniquíes.

Antes de recogida formal de datos identificables de menores, confirmar
requisitos éticos/académicos.

# 13. Fuera de alcance inicial

-   diagnóstico médico;
-   predicción de enfermedades;
-   detección de hambre;
-   clasificación de causas del llanto;
-   monitorización fisiológica clínica;
-   reconocimiento facial;
-   identificación biométrica;
-   entrenamiento de foundation models;
-   Kubernetes/EKS por defecto;
-   microservicios innecesarios.

# 14. Arquitectura lógica

``` text
CAMERA (Tapo C220)
        │ RTSP A/V
        ▼
ACQUISITION
   ┌────┴────┐
   ▼         ▼
VIDEO       AUDIO
PIPELINE    PIPELINE
   │         │
YOLO/...   CRY MODEL
   └────┬────┘
        ▼
CONTEXT/TIME ENGINE
        ▼
EVENT ENGINE
   ┌────┴─────┐
   ▼          ▼
DATABASE    BACKEND
              │
         ┌────┴────┐
         ▼         ▼
       PUSH     MOBILE APP
```

# 15. Milestones

## M0 --- Proof of Concept

Validado actualmente:

``` text
Tapo C220 → RTSP → OpenCV → YOLO11n
→ RTX 5070 → detecciones
```

## M1 --- Captura RTSP estable

Implementar módulo RTSP, latest-frame capture, configuración externa,
manejo de errores, métricas y tests.

## M2 --- Pipeline visual base

``` text
latest frame → YOLO → structured detections
```

Añadir timestamps, inference latency, FPS, device information e
interfaces desacopladas.

## M3 --- Estado y tracking temporal

Introducir estados, duración, persistencia y tracking cuando sea
necesario.

## M4 --- Situaciones visuales

Implementar progresivamente boca abajo, rostro cubierto, objeto próximo,
zona crítica, intento de salida y ausencia.

Cada funcionalidad debe validarse antes de añadir la siguiente.

## M5 --- Audio

``` text
RTSP audio → acoustic model → cry state
```

Integración temporal con estados visuales.

## M6 --- Event Engine

``` text
visual states + audio states + time + spatial context
→ events → alert levels
```

## M7 --- Backend y persistencia

API, eventos, estados, almacenamiento e historial.

## M8 --- Aplicación móvil

Estado actual, historial, notificaciones, configuración y vídeo en vivo.

## M9 --- Streaming remoto

Evaluar e implementar tecnología seleccionada. WebRTC es candidato.

## M10 --- Integración end-to-end

``` text
escenario → cámara → IA → motor temporal
→ evento → backend → notificación → app → cuidador
```

## M11 --- Evaluación TFM

Medir precisión, recall, F1, falsas alarmas, latencia, tiempo hasta
alerta, rendimiento, robustez y comportamiento end-to-end.

# 16. Definition of Done

Una funcionalidad no se considera terminada solo porque funcione
localmente.

Cuando corresponda debe incluir:

-   código implementado;
-   configuración separada;
-   manejo de errores;
-   logging;
-   tests;
-   métricas;
-   documentación;
-   ausencia de secretos;
-   ausencia de datos personales en Git;
-   criterios de aceptación comprobados.

# 17. Prioridad inmediata

No comenzar todavía con cloud, backend complejo, app completa,
Kubernetes o microservicios.

Prioridad:

``` text
M1: RTSP estable
↓
M2: pipeline YOLO limpio
↓
M3: representación temporal de estados
```

Construir incrementalmente y validar cada capa antes de añadir la
siguiente.
