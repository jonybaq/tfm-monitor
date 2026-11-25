"""Receive camera commands over an outbound WebSocket."""

import json
from collections.abc import Callable
from functools import partial
from time import sleep
from urllib.parse import urlsplit

from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

from .tapo_controls import (
    MODES,
    CameraControlError,
    MovementLimitError,
    microphone_settings,
    move_camera,
    restore_view,
    save_view,
    set_day_night_mode,
    set_microphone_mute,
)
from .tapo_login import read_settings

RESULT_LABELS = {
    "accepted": "PyTapo aceptó la orden",
    "rejected": "orden rechazada",
    "camera_error": "la cámara devolvió un error",
    "movement_limit": "la cámara alcanzó el límite en esa dirección",
}


def _day_night_state(camera) -> dict:
    mode = camera.getDayNightMode()
    if mode not in MODES.values():
        raise CameraControlError("La cámara no informa un modo día/noche válido.")
    return {"state": mode}


def _microphone_state(camera) -> dict:
    settings = microphone_settings(camera)
    state = {"state": settings["mute"]}
    volume = str(settings.get("volume", ""))
    if volume.isascii() and volume.isdigit() and len(volume) <= 3 and int(volume) <= 100:
        state["volume"] = int(volume)
    return state


def _actions(camera) -> dict:
    return {
        "move_left": ("mover a la izquierda", partial(move_camera, camera, "izquierda")),
        "move_right": ("mover a la derecha", partial(move_camera, camera, "derecha")),
        "move_up": ("mover arriba", partial(move_camera, camera, "arriba")),
        "move_down": ("mover abajo", partial(move_camera, camera, "abajo")),
        "save_view": ("guardar encuadre", partial(save_view, camera)),
        "restore_view": ("recuperar encuadre", partial(restore_view, camera)),
        "get_day_night": ("consultar modo día/noche", partial(_day_night_state, camera)),
        "set_day": ("activar modo Día", partial(set_day_night_mode, camera, "off")),
        "set_night": ("activar modo Noche", partial(set_day_night_mode, camera, "on")),
        "set_auto": ("activar modo Automático", partial(set_day_night_mode, camera, "auto")),
        "get_microphone": ("consultar micrófono", partial(_microphone_state, camera)),
        "mute_microphone": ("silenciar micrófono", partial(set_microphone_mute, camera, True)),
        "unmute_microphone": ("reactivar micrófono", partial(set_microphone_mute, camera, False)),
    }


def command_result(camera, message: str | bytes) -> dict:
    result = {"id": None, "status": "rejected"}
    if not isinstance(message, str):
        return result
    try:
        command = json.loads(message)
    except (ValueError, RecursionError):
        return result
    if not isinstance(command, dict):
        return result
    command_id = command.get("id")
    if not isinstance(command_id, str) or not 1 <= len(command_id) <= 64:
        return result
    result["id"] = command_id
    action = command.get("action")
    selected = _actions(camera).get(action) if isinstance(action, str) else None
    if selected is None:
        return result
    label, execute = selected
    print(f"Orden del servidor WebSocket: {label}.", flush=True)
    try:
        details = execute()
    except MovementLimitError as error:
        print(error, flush=True)
        result["status"] = "movement_limit"
    except Exception as error:
        if type(error) is not Exception and not isinstance(error, (OSError, CameraControlError)):
            raise
        result["status"] = "camera_error"
    else:
        result["status"] = "accepted"
        if action in {"get_day_night", "get_microphone"}:
            result.update(details)
    return result


def run_remote(
    camera, url: str, token: str, *, on_connected: Callable[[], None] | None = None,
) -> None:
    address = urlsplit(url)
    local_test = address.scheme == "ws" and address.hostname in {"127.0.0.1", "::1"}
    if (
        not address.hostname or address.username is not None or address.fragment
        or (address.scheme != "wss" and not local_test)
    ):
        raise ValueError("Usa una URL wss://. ws:// solo se admite en loopback para pruebas.")
    if not token or not token.isascii() or not token.isprintable() or any(c.isspace() for c in token):
        raise ValueError("Configura CAMERA_CONTROL_WS_TOKEN con un token válido.")

    with connect(
        url, additional_headers={"Authorization": f"Bearer {token}"},
        proxy=None, max_size=4096, open_timeout=5, close_timeout=2,
    ) as websocket:
        print("WebSocket conectado. Esperando órdenes.")
        if on_connected is not None:
            on_connected()
        for message in websocket:
            result = command_result(camera, message)
            print(f"Resultado: {RESULT_LABELS[result['status']]}.", flush=True)
            websocket.send(json.dumps(result))


def run_remote_from_config(camera, choose_action) -> None:
    settings = read_settings()
    url = settings.get("CAMERA_CONTROL_WS_URL", "")
    token = settings.get("CAMERA_CONTROL_WS_TOKEN", "")
    attempt = 0

    def reset_attempts() -> None:
        nonlocal attempt
        attempt = 0

    while True:
        if attempt:
            print(f"Reconectando al servidor WebSocket ({attempt}/3)...", flush=True)
            sleep(2)
        try:
            run_remote(camera, url, token, on_connected=reset_attempts)
        except ValueError as error:
            print(error)
            return
        except (OSError, WebSocketException):
            print("No se pudo abrir o mantener el canal WebSocket.")
        else:
            print("El servidor cerró la conexión WebSocket.")
        if attempt == 3:
            if choose_action(("Volver al menú principal", "Seguir reintentando")) == 0:
                return
            attempt = 0
        else:
            attempt += 1
