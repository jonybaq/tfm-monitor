# Canal WebSocket del backend

El servidor acepta una conexión de `camera_control`. El menú permite mover
en cuatro direcciones, guardar y recuperar encuadre, consultar y cambiar
el modo día/noche y consultar, silenciar o reactivar el micrófono.
Cada orden lleva un ID y el servidor espera la respuesta
de ese ID. Si el controlador se desconecta o agota el tiempo, muestra
que la orden quedó sin confirmar. La consola solo escucha en loopback.

## Prueba con la cámara desde Windows

Desde la raíz del repositorio, instala los requisitos si todavía faltan:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt -r camera_control/requirements.txt
```

El servidor lee `CAMERA_CONTROL_WS_TOKEN` de `backend/.env`. La cámara
lee el mismo token y la URL `ws://127.0.0.1:8765/camera` de
`camera_control/.env`. Ambos archivos están excluidos de Git. En una
instalación nueva, copia los campos de los ejemplos y usa el mismo token
privado en ambos archivos.

En la primera terminal, inicia el servidor:

```powershell
.\.venv\Scripts\python.exe -m backend
```

En una segunda terminal, inicia el controlador:

```powershell
.\.venv\Scripts\python.exe -m camera_control
```

Selecciona **Conectar al servidor WebSocket** en la segunda terminal.
Cuando muestre **WebSocket conectado**, selecciona
**Mover a la izquierda** en la primera. Comprueba un giro corto en la cámara.
La consola informa si PyTapo aceptó la orden. Para cerrar, selecciona
**Salir** en la consola del servidor.

Pruebas automatizadas con un cliente WebSocket simulado:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```

## API REST local y Postman

Inicia el backend en modo API. FastAPI sirve REST y WebSocket en el mismo
puerto, `8080`. La documentación interactiva está en
`http://127.0.0.1:8080/docs`.

```powershell
.\.venv\Scripts\python.exe -m backend --api
```

Configura `CAMERA_CONTROL_WS_URL=ws://127.0.0.1:8080/camera` en
`camera_control/.env`. En otra terminal inicia `python -m camera_control` con el entorno del proyecto
y elige **Conectar al servidor WebSocket**. Importa
`camera-control.postman_collection.json` en Postman. Configura la variable
local `apiToken` con el valor de `CAMERA_CONTROL_API_TOKEN` de
`backend/.env`. Este token es distinto del token WebSocket.

- `GET /api/v1/camera/day-night` y `GET /api/v1/camera/microphone` consultan el estado.
- `POST /api/v1/camera/actions/{action}` envía una acción del menú sin cuerpo HTTP.
- La API responde `200` si PyTapo acepta la orden, `401` si el token no es válido,
  `409` si el motor informa el límite o hay una orden en curso, `503` si el
  controlador está desconectado y `504` si no hay confirmación a tiempo.

La API escucha en `127.0.0.1:8080` para esta primera versión local.

## Docker local

Detén el backend ejecutado directamente en la laptop antes de levantar el
contenedor. Desde la raíz del repositorio:

```powershell
docker compose -f backend/compose.yaml up --build -d
docker compose -f backend/compose.yaml logs -f backend
```

Compose inyecta los tokens de `backend/.env` al arrancar. El contenedor
publica REST en `http://127.0.0.1:8080` y WebSocket en
`ws://127.0.0.1:8080/camera`. Usa la misma colección de Postman y ejecuta
`camera_control` en la laptop como antes.

Para detener el contenedor:

```powershell
docker compose -f backend/compose.yaml down
```
