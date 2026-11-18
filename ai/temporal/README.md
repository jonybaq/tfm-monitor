# Motor temporal — M3

Recibe señales abstractas con nombre, valor activo/inactivo y timestamp. Mantiene
su inicio, última evidencia y duración; una señal inactiva finaliza el estado.
No conoce YOLO, cámara, audio, reglas de riesgo ni alertas.

El motor mide duración pero no decide umbrales. Un componente posterior decidirá,
con valores configurables y validados, cuándo reportar un evento.

## Pruebas

Usa el entorno compartido descrito en el [README general](../../README.md).

Desde `ai/temporal/`:

```powershell
..\..\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Demo en consola

```powershell
..\..\.venv\Scripts\python.exe -m scripts.demo
```

La demo usa una señal sintética; no define umbrales del sistema.
