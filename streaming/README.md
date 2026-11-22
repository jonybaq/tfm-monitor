# Envío de vídeo y audio de la Tapo

El módulo inicia y supervisa FFmpeg para enviar la señal de la Tapo por SRT.
Reutiliza la conexión RTSP de `capture/.env` y el entorno virtual de la raíz.

El menú inicial ofrece **FFmpeg por comando** y **PyAV · RTSP experimental**.
Para probar PyAV en Windows desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m pip install av
.\.venv\Scripts\python.exe -m streaming
```

PyAV usa las bibliotecas incluidas en su paquete precompilado y abre la
cámara y el destino dentro de Python. Las credenciales siguen en la
configuración local y quedan fuera de los argumentos de los procesos.
En el paquete probado, PyAV publica por RTSP. Para SRT, selecciona
**FFmpeg por comando**. Para la primera prueba con PyAV, usa **Local** con
MediaMTX iniciado.
Al iniciar, muestra **Comprobando instalación de FFmpeg** y busca el ejecutable
en `PATH` y en la instalación de WinGet. Al encontrarlo, muestra un **✓ verde**
y continúa. Los puntos de espera se sustituyen por el resultado en la misma
línea. Si falta y WinGet está disponible, ofrece instalarlo mediante un
menú vertical **Sí / No**. Usa **↑ / ↓** y confirma con **Enter**. Si eliges **No**
o la instalación falla, muestra una **✗ roja** y termina con el mensaje
«Se necesita FFmpeg para establecer la conexión».

Después revisa `capture/.env`. Si falta algún dato RTSP, solicita solo los
valores faltantes y los guarda ahí. La contraseña se introduce de forma
oculta. El lanzador prueba que llegue un fotograma durante un máximo de
60 segundos. En PowerShell, la cuenta regresiva se actualiza en la misma
línea. Si no llega, indica qué revisar y termina. Tras recibirlo,
muestra el menú de destino.

Los destinos se guardan en `streaming/.env`, que Git ignora. Usa
`streaming/.env.example` como referencia. El emisor pide solo los datos
faltantes del modo elegido y los guarda después de validarlos. En modo local
puedes aceptar `127.0.0.1` y el puerto SRT `8890` con **Enter**. En Azure se
piden la IP pública o DNS de `tapo-media`, el puerto y la frase de publicación
si aún no están configurados. Puedes editar los destinos y puertos en el archivo.

Al elegir un modo, desaparecen la pregunta y las opciones. El paso **3**
registra el modo elegido, el **4** indica el protocolo y el **5** muestra
el destino y una cuenta regresiva de hasta 60 segundos. Se confirma cuando
FFmpeg empieza a publicar. Si el receptor no acepta la conexión en ese plazo, el
programa termina. Después de una publicación exitosa, los cortes se
reintentan con la supervisión normal.

Durante el envío, la misma consola muestra los fotogramas, FPS, tiempo
transmitido, bitrate y velocidad. Esa línea se actualiza con el progreso
de FFmpeg.

## Probar en local

Desde la raíz, con Docker Desktop abierto, inicia un receptor de prueba para
SRT y RTSP.
El receptor escucha solo en esta laptop.

```powershell
docker run --rm -d --name tfm-streaming-receiver -p 127.0.0.1:8890:8890/udp -p 127.0.0.1:8554:8554/tcp -p 127.0.0.1:8891:8889/tcp -p 127.0.0.1:8190:8190/udp -e MTX_WEBRTCADDITIONALHOSTS=127.0.0.1 -e MTX_WEBRTCLOCALUDPADDRESS=:8190 bluenviron/mediamtx:1.21.4
```

Desde una terminal nueva, en la raíz del proyecto, inicia el emisor:

```powershell
.\.venv\Scripts\python.exe -m streaming
```

En el menú vertical, elige **Local** con **↑ / ↓** y pulsa **Enter**. Si ya configuraste
`STREAMING_MODE` en esa terminal, el programa usa ese modo directamente.
En local puedes elegir **SRT** (puerto `8890`) o **RTSP** (puerto TCP `8554`).
Para comparar la latencia, detén el emisor entre pruebas y usa el mismo
reproductor. En Azure, el protocolo habitual es SRT.

Para probar un búfer de entrada reducido, ejecuta
`$env:STREAMING_LOW_LATENCY = 'on'` antes de iniciar el emisor y elige
**Local → RTSP**. Compara el tiempo hasta la primera imagen y el retraso
después de 30 segundos con `$env:STREAMING_LOW_LATENCY = 'off'`.
El ajuste conserva el vídeo y el audio del flujo habitual.
En la prueba con la Tapo, el búfer reducido adelantó la imagen y dejó el
audio atrasado. Omitir el filtro de marcas de tiempo produjo cortes. Para
ver vídeo y audio juntos, usa el modo habitual con el búfer normal.

Cuando aparezca `Enviando vídeo y audio (local)`, abre el
[directo de prueba](http://127.0.0.1:8891/tapo/?muted=false&autoplay=false)
y pulsa **Reproducir**. Para verificar la espera, puedes arrancar el emisor
antes del receptor y abrir otra terminal para iniciar el contenedor. Para
verificar la recuperación, detén el receptor con
`docker stop tfm-streaming-receiver` y vuelve a ejecutar el comando
`docker run` mientras el emisor sigue abierto. También puedes apagar y
encender la Tapo para probar la espera de cámara.

Pulsa **Ctrl+C** en la terminal del emisor y ejecuta
`docker stop tfm-streaming-receiver` para terminar la prueba.

## Enviar a Azure

Para el envío habitual, elige **Azure → SRT**.

Con `tapo-media` preparado, usa una escena de prueba. Ejecuta
`.\.venv\Scripts\python.exe -m streaming`, elige **Azure** con las flechas,
pulsa **Enter** e introduce la IP y
la frase SRT de publicación cuando se pidan.

**Azure → RTSP** es una prueba temporal con una escena sin datos personales.
Requiere desplegar la plantilla de prueba con **8554/TCP** y publicación
autenticada. Usa el mismo `STREAMING_AZURE_HOST` que SRT, el puerto
`STREAMING_AZURE_RTSP_PORT=8554` y la contraseña temporal de publicación
que pide el emisor y guarda en `streaming/.env`. La misma contraseña se usa
para autenticar SRT mientras esté desplegada esa plantilla. SRT sigue
requiriendo su propia frase de cifrado. El enlace WebRTC se mantiene.

Para ejecutar sin el menú, puedes configurar el destino previamente:

```powershell
$env:STREAMING_MODE = 'azure'
$env:STREAMING_HOST = Read-Host 'IP publica de tapo-media'
$env:STREAMING_SRT_PASSPHRASE = Read-Host 'Frase SRT de publicacion'
try {
    .\.venv\Scripts\python.exe -m streaming
} finally {
    Remove-Item Env:STREAMING_SRT_PASSPHRASE -ErrorAction SilentlyContinue
}
```

Abre `http://IP_PUBLICA:8889/tapo/?muted=false&autoplay=false`, sustituyendo
`IP_PUBLICA` por la IP que introdujiste, y pulsa **Reproducir**. Si se corta
la transmisión, el lanzador informa del corte y vuelve a intentar con una
pausa de tres segundos entre intentos.

El flujo usa H.264 de la cámara y Opus para el audio. El ajuste de marcas de
tiempo presupone 30 FPS. El modo habitual requiere ambas pistas.
Para una prueba sin audio, ejecuta `$env:STREAMING_AUDIO = 'off'` antes de
iniciar el emisor. Usa `'on'` para volver a enviar ambas pistas.

## Ejecutar las pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s streaming/tests -v
```
