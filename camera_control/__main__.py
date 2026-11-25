"""Consola local para comprobar el encuadre de la Tapo."""

from collections.abc import Callable
from functools import partial
import sys

from capture.rtsp.config import RtspConfig, RtspConfigurationError
from .ptz import CameraController, CameraControlError, DIRECTIONS, ONVIF_PORT


def choose_action(labels: tuple[str, ...]) -> int:
    from msvcrt import getwch

    selected = 0
    print("Usa ↑ / ↓ y pulsa Enter. Esc para salir.")
    while True:
        for index, label in enumerate(labels):
            print(f"{'>' if index == selected else ' '} {label}")
        step = read_menu_step(getwch)
        if step == 0:
            return selected
        selected = (selected + step) % len(labels)
        print(f"\033[{len(labels)}A", end="", flush=True)


def read_menu_step(read_key: Callable[[], str]) -> int:
    """Convert Windows keyboard input into a selection step or Enter."""
    arrow_steps = {"H": -1, "P": 1}
    while True:
        key = read_key()
        if key in {"\x03", "\x1b"}:
            raise KeyboardInterrupt
        if key == "\r":
            return 0
        if key in {"\x00", "\xe0"}:
            step = arrow_steps.get(read_key())
            if step is not None:
                return step


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
    print("1. Comprobando la instalación de ONVIF...", flush=True)
    try:
        from onvif.exceptions import ONVIFError
    except ImportError:
        print("[ERROR] La dependencia ONVIF no está disponible.")
        print(r"Instala las dependencias con .\.venv\Scripts\python.exe -m pip install -r camera_control/requirements.txt")
        return 1
    print("[OK] Dependencia ONVIF disponible.")
    try:
        controller = initialize_camera(ONVIFError)
        if controller is None:
            return 1
        run_menu(controller, ONVIFError)
    except KeyboardInterrupt:
        return 0
    return 0


def initialize_camera(protocol_error: type[Exception]) -> CameraController | None:
    print("2. Verificando la configuración de la cámara...", flush=True)
    try:
        config = RtspConfig.from_environment()
    except RtspConfigurationError as error:
        print(f"[ERROR] {error} Revisa capture/.env.")
        return None
    except OSError:
        print("[ERROR] No se pudo leer capture/.env.")
        return None
    print("[OK] Configuración de cámara válida.")

    host = config.host
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    print(f"3. Conectando por ONVIF a {host}:{ONVIF_PORT}...", flush=True)
    try:
        controller = CameraController.connect(config)
    except CameraControlError as error:
        print(f"[ERROR] {error}")
        return None
    except (protocol_error, OSError):
        print("[ERROR] No se pudo conectar por ONVIF. Revisa la cuenta de cámara y la red local.")
        return None
    print("[OK] Conexión ONVIF y perfil de movimiento disponibles.")
    return controller


if __name__ == "__main__":
    raise SystemExit(main())
