"""Controls for testing the camera directly through PyTapo."""

import re
from functools import partial

PRESET_NAME = "TFM PyTapo"
MOVE_STEP = 5
MOVES = {
    "izquierda": (-MOVE_STEP, 0), "derecha": (MOVE_STEP, 0),
    "arriba": (0, MOVE_STEP), "abajo": (0, -MOVE_STEP),
}
MODES = {"Día": "off", "Noche": "on", "Automático": "auto"}


class CameraControlError(Exception):
    """A control operation could not be confirmed."""


class MovementLimitError(CameraControlError):
    """The camera reported its pan or tilt limit."""


def move_camera(camera, direction: str) -> None:
    destination = f"la {direction}" if direction in {"izquierda", "derecha"} else direction
    message = f"La cámara ya no puede moverse más hacia {destination}."
    try:
        response = camera.moveMotor(*MOVES[direction])
    except Exception as error:
        details = str(error)
        if "MOTOR_LOCKED_ROTOR" not in details and not re.search(
            r'"error_code"\s*:\s*(?:-64304\b|"-64304")', details,
        ):
            raise
        raise MovementLimitError(message) from None
    if isinstance(response, dict) and response.get("error_code") in (-64304, "-64304"):
        raise MovementLimitError(message)


def find_view(camera):
    latest = (0, None)
    for preset_id, name in camera.getPresets().items():
        if name == PRESET_NAME and latest[1] is None:
            latest = (0, preset_id)
        elif name.startswith(f"{PRESET_NAME} "):
            revision = name[len(PRESET_NAME) + 1:]
            if revision.isascii() and revision.isdigit() and int(revision) > latest[0]:
                latest = (int(revision), preset_id)
    return latest


def save_view(camera) -> None:
    revision, previous_id = find_view(camera)
    name = f"{PRESET_NAME} {revision + 1}"
    camera.savePreset(name)
    if name not in camera.getPresets().values():
        raise CameraControlError("PyTapo no encontró el encuadre después de guardarlo.")
    print("Encuadre de prueba guardado.")
    if previous_id is not None:
        camera.deletePreset(previous_id)


def restore_view(camera) -> None:
    _, preset_id = find_view(camera)
    if preset_id is None:
        raise CameraControlError("Guarda primero un encuadre de prueba.")
    camera.setPreset(preset_id)
    print("Orden aceptada. Comprueba el encuadre en el directo.")


def night_mode(camera, choose_action) -> None:
    current = camera.getDayNightMode()
    label = next((name for name, value in MODES.items() if value == current), "Desconocido")
    print(f"Modo actual: {label}.")
    choices = tuple(MODES) + ("Volver",)
    selected = choose_action(choices)
    if selected < len(MODES):
        set_day_night_mode(camera, MODES[choices[selected]])
        print(f"Modo confirmado: {choices[selected]}.")


def set_day_night_mode(camera, mode: str) -> None:
    camera.setDayNightMode(mode)
    if camera.getDayNightMode() != mode:
        raise CameraControlError("La cámara todavía no confirma el modo solicitado.")


def microphone_settings(camera) -> dict:
    microphone = camera.getAudioConfig().get("audio_config", {}).get("microphone", {})
    if microphone.get("mute") not in {"on", "off"}:
        raise CameraControlError("La cámara no informa el estado de silencio del micrófono.")
    return microphone


def microphone_menu(camera, choose_action) -> None:
    current = microphone_settings(camera)
    muted = current["mute"] == "on"
    print(f"Micrófono de la cámara: {'silenciado' if muted else 'activo'}.")
    if "volume" in current:
        print(f"Volumen de captación: {current['volume']}.")
    action = "Reactivar micrófono" if muted else "Silenciar micrófono"
    print("Silenciar la cámara afecta al audio de origen y al análisis de llanto.")
    if choose_action(("Volver", action)) == 0:
        return

    set_microphone_mute(camera, not muted)
    print(f"Micrófono confirmado: {'activo' if muted else 'silenciado'}.")


def set_microphone_mute(camera, muted: bool) -> None:
    camera.setMicrophone(mute=muted)
    expected = "on" if muted else "off"
    if microphone_settings(camera)["mute"] != expected:
        raise CameraControlError("La cámara todavía no confirma el cambio del micrófono.")


def run_tapo_menu(camera, choose_action) -> None:
    labels = tuple(f"Mover {direction}" for direction in MOVES) + (
        "Guardar encuadre de prueba", "Volver al encuadre de prueba",
        "Consultar o cambiar modo día/noche", "Consultar o controlar micrófono", "Salir",
    )
    actions = [partial(move_camera, camera, direction) for direction in MOVES]
    actions.extend((partial(save_view, camera), partial(restore_view, camera),
                    partial(night_mode, camera, choose_action),
                    partial(microphone_menu, camera, choose_action)))
    while (selected := choose_action(labels)) < len(actions):
        try:
            actions[selected]()
        except CameraControlError as error:
            print(error)
        except Exception as error:
            # PyTapo raises plain Exception for rejected camera operations.
            if type(error) is not Exception and not isinstance(error, OSError):
                raise
            print("PyTapo no pudo completar esa orden.")
        else:
            if selected < len(MOVES):
                print("Orden aceptada. Comprueba el movimiento en el directo.")
