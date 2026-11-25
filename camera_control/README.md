# Control local de la cámara Tapo

El módulo usa PyTapo por el puerto 443 para mover la cámara, guardar y
recuperar el encuadre de supervisión y cambiar el modo Día, Noche o Automático.
Usa la dirección de la cámara configurada en `capture/.env`.

Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m pip install -r camera_control/requirements.txt
.\.venv\Scripts\python.exe -m camera_control
```

La primera vez, pulsa Enter para usar `admin` o escribe otro usuario.
Introduce la contraseña de la cuenta Tapo. La entrada se mantiene oculta.
Si la cámara acepta la sesión, el programa guarda la configuración en
`camera_control/.env`, excluido de Git, y la reutiliza al volver a iniciar.
Para cambiarla, retira las dos entradas de PyTapo del archivo y vuelve a
ejecutar el programa.

Usa las flechas y Enter para elegir un control. Guarda un encuadre, mueve
la cámara y comprueba que vuelve al mismo sitio al recuperar el encuadre.
Si pruebas el modo día/noche, vuelve al modo inicial al terminar.

**Consultar o controlar micrófono** muestra su estado y volumen de captación.
Para probarlo, abre el directo por RTSP, silencia el micrófono desde el
menú y comprueba que deja de oírse el audio de origen. Reactívalo y comprueba
que vuelve el sonido. Silenciar el micrófono afecta al análisis de llanto.

Pruebas unitarias sin cámara ni red:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s camera_control/tests
```

## Cliente WebSocket de prueba

La opción **Conectar al servidor WebSocket** abre una conexión saliente al
servidor configurado en `camera_control/.env`. Usa `CAMERA_CONTROL_WS_URL`
y `CAMERA_CONTROL_WS_TOKEN`.
Usa `wss://` fuera de loopback. Para probar con tu cámara, sigue los pasos del
[servidor local](../backend/README.md). Con las variables configuradas,
ejecuta:

```powershell
.\.venv\Scripts\python.exe -m camera_control
```

El servidor puede enviar `{"id":"orden-1","action":"move_left"}` o cualquiera
de los demás controles del menú del backend.
El cliente devuelve el mismo ID y un estado `accepted`, `rejected` o
`camera_error`. Si PyTapo informa que alcanzó el tope del motor, el cliente
devuelve `movement_limit`. Las consultas devuelven además el estado solicitado.
Si se pierde la conexión, el cliente reintenta hasta tres veces con dos
segundos de espera entre intentos. Si sigue sin conectar, el menú permite
seguir intentando o volver al menú principal.
La prueba automatizada usa un servidor en loopback y una cámara simulada:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s camera_control/tests -p test_remote.py
```
