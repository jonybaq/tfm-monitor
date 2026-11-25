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

Pruebas unitarias sin cámara ni red:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s camera_control/tests
```
