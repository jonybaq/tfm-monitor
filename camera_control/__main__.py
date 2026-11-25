"""Consola local para comprobar el encuadre de la Tapo."""

from functools import partial
import sys

from capture.rtsp.config import RtspConfig, RtspConfigurationError
from .ptz import CameraController, CameraControlError, DIRECTIONS


def choose_action(labels: tuple[str, ...]) -> int:
    from msvcrt import getwch

    selected = 0
    print("Usa ↑ / ↓ y pulsa Enter. Esc para salir.")
    while True:
        for index, label in enumerate(labels):
            print(f"{'>' if index == selected else ' '} {label}")
        while True:
            key = getwch()
            if key in {"\x03", "\x1b"}:
                raise KeyboardInterrupt
            if key == "\r":
                return selected
            if key in {"\x00", "\xe0"}:
                arrow = getwch()
                if arrow in {"H", "P"}:
                    selected = (selected + (-1 if arrow == "H" else 1)) % len(labels)
                    print(f"\033[{len(labels)}A", end="", flush=True)
                    break


def run_menu(controller: CameraController, protocol_error: type[Exception]) -> None:
    actions = [partial(controller.move, direction) for direction in DIRECTIONS]
    labels = tuple(f"Mover {direction}" for direction in DIRECTIONS) + (
        "Guardar encuadre de supervisión", "Volver al encuadre de supervisión", "Salir",
    )
    actions.extend((controller.save_view, controller.restore_view))
    while (selected := choose_action(labels)) < len(actions):
        try:
            actions[selected]()
        except CameraControlError as error:
            print(error)
        except (protocol_error, OSError):
            print("La cámara no aceptó la orden ONVIF. Revisa la conexión y la compatibilidad.")
        else:
            print("Orden aceptada por la cámara.")


def main() -> int:
    if sys.platform != "win32" or not sys.stdin.isatty():
        print("Ejecuta el control de cámara desde una terminal interactiva de Windows.")
        return 1
    try:
        from onvif.exceptions import ONVIFError
    except ImportError:
        print(r"Instala las dependencias con .\.venv\Scripts\python.exe -m pip install -r camera_control/requirements.txt")
        return 1
    try:
        controller = CameraController.connect(RtspConfig.from_environment())
        run_menu(controller, ONVIFError)
    except KeyboardInterrupt:
        return 0
    except (CameraControlError, RtspConfigurationError) as error:
        print(error)
        return 1
    except (ONVIFError, OSError):
        print("No se pudo conectar por ONVIF. Revisa la cuenta de cámara y la red local.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
