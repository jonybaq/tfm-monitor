# Control local de la cámara Tapo

La HU-12 añade control de giro, inclinación y encuadre desde Windows.
El módulo se ejecuta por separado y usa la cuenta local de cámara que ya
está configurada en `capture/.env`. ONVIF usa el puerto 2020 en la red local.

Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m pip install -r camera_control/requirements.txt
.\.venv\Scripts\python.exe -m camera_control
```

Al arrancar, la consola muestra la comprobación de ONVIF, la validación de
`capture/.env` y la dirección de la cámara. El menú aparece cuando la
conexión ONVIF y el perfil de movimiento están disponibles.

En el encuadre de la cuna, selecciona **Guardar encuadre de supervisión**.
Prueba los cuatro movimientos y selecciona **Volver al encuadre de
supervisión**. Verifica que la cámara recupera la posición y que el directo
continúa en la otra terminal. El encuadre se guarda en la cámara si el
firmware admite posiciones ONVIF.

**Consultar o cambiar modo nocturno** muestra el filtro infrarrojo actual
y solo ofrece los modos anunciados por el firmware mediante ONVIF.
Si la cámara no expone esa capacidad, el ajuste sigue disponible en la app
Tapo. Prueba el cambio con el directo abierto y restaura el modo anterior
al terminar.

Pruebas unitarias sin cámara ni red:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s camera_control/tests
```
