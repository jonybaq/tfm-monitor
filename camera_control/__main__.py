"""Consola local para comprobar el encuadre de la Tapo."""

from collections.abc import Callable
import sys

from capture.rtsp.config import RtspConfig, RtspConfigurationError
from .tapo_controls import run_tapo_menu
from .tapo_login import connect_tapo


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


def main() -> int:
    if sys.platform != "win32" or not sys.stdin.isatty():
        print("Ejecuta el control de cámara desde una terminal interactiva de Windows.")
        return 1
    try:
        camera = connect_tapo(RtspConfig.from_environment().host)
        if camera is None:
            return 1
        run_tapo_menu(camera, choose_action)
    except RtspConfigurationError as error:
        print(f"[ERROR] {error} Revisa capture/.env.")
        return 1
    except OSError:
        print("No se pudo leer o guardar la configuración local.")
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
