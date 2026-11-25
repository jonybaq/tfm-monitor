# Control local de la cámara Tapo

La HU-12 añade control de giro, inclinación y encuadre desde Windows.
El módulo se ejecuta por separado y usa la cuenta local de cámara que ya
está configurada en `capture/.env`. ONVIF usa el puerto 2020 en la red local.

Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m pip install -r camera_control/requirements.txt
.\.venv\Scripts\python.exe -m camera_control
```

En el encuadre de la cuna, selecciona **Guardar encuadre de supervisión**.
Prueba los cuatro movimientos y selecciona **Volver al encuadre de
supervisión**. Verifica que la cámara recupera la posición y que el directo
continúa en la otra terminal. El encuadre se guarda en la cámara si el
firmware admite posiciones ONVIF.

Pruebas unitarias sin cámara ni red:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s camera_control/tests
```
