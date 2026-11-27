"""Local console for sending commands through the camera WebSocket."""

import sys
from pathlib import Path
from threading import Thread

from .camera_socket import COMMANDS, CameraChannel, local_server

RESULTS = {
    "accepted": "PyTapo aceptó la orden.",
    "rejected": "El controlador rechazó la orden.",
    "camera_error": "El controlador no pudo completar la orden.",
    "movement_limit": "La cámara alcanzó el límite de movimiento en esa dirección.",
    "unconfirmed": "La orden quedó sin confirmar.",
    "offline": "El controlador todavía no está conectado.",
    "busy": "Hay una orden en curso.",
}
ENV_FILE = Path(__file__).with_name(".env")


def read_token(setting: str = "CAMERA_CONTROL_WS_TOKEN") -> str:
    configured_value = ""
    if ENV_FILE.is_file():
        for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == setting:
                configured_value = value.strip()
    return configured_value


def run_console(channel: CameraChannel) -> None:
    from msvcrt import getwch

    actions = tuple(COMMANDS)
    labels = (*COMMANDS.values(), "Salir")
    selected = 0
    print("Usa ↑ / ↓ y Enter. Esc para salir.")
    while True:
        for index, label in enumerate(labels):
            print(f"{'>' if index == selected else ' '} {label}")
        while True:
            key = getwch()
            if key in {"\x1b", "\x03"}:
                return
            if key == "\r":
                if selected == len(actions):
                    return
                action = actions[selected]
                if action == "mute_microphone":
                    print("El silencio del micrófono afecta al análisis de llanto.")
                show_result(action, channel.send_command(action))
                break
            if key in {"\x00", "\xe0"}:
                step = {"H": -1, "P": 1}.get(getwch())
                if step is not None:
                    selected = (selected + step) % len(labels)
                    print(f"\033[{len(labels)}A", end="", flush=True)
                    break


def show_result(action: str, result: dict) -> None:
    print(RESULTS[result["status"]])
    state = result.get("state")
    if action == "get_day_night" and state is not None:
        print(f"Modo actual: { {'off': 'Día', 'on': 'Noche', 'auto': 'Automático'}[state] }.")
    if action == "get_microphone" and state in ("on", "off"):
        print(f"Micrófono: {'silenciado' if state == 'on' else 'activo'}.")
        if "volume" in result:
            print(f"Volumen de captación: {result['volume']}.")


def main() -> int:
    api_mode = sys.argv[1:] == ["--api"]
    if not api_mode and (sys.platform != "win32" or not sys.stdin.isatty()):
        print("Ejecuta la consola WebSocket desde una terminal interactiva de Windows.")
        return 1
    try:
        channel = CameraChannel(read_token())
        with local_server(channel) as server:
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                print("Servidor escuchando en ws://127.0.0.1:8765/camera.")
                if api_mode:
                    from .http_api import create_http_server

                    with create_http_server(channel, read_token("CAMERA_CONTROL_API_TOKEN")) as api:
                        print("API escuchando en http://127.0.0.1:8080.", flush=True)
                        api.serve_forever()
                else:
                    run_console(channel)
            finally:
                server.shutdown()
                channel.close()
                thread.join()
    except ValueError as error:
        print(error)
        return 1
    except OSError:
        print("No se pudo iniciar o mantener el servidor local. Revisa los puertos 8765 y 8080.")
        return 1
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
