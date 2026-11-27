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

Inicia el backend en modo API. Este proceso también levanta el WebSocket:

```powershell
.\.venv\Scripts\python.exe -m backend --api
```

En otra terminal inicia `python -m camera_control` con el entorno del proyecto
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
