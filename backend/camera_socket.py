"""WebSocket channel for one connected camera controller."""

import json
from hmac import compare_digest
from http import HTTPStatus
from threading import Condition, Lock
from uuid import uuid4

from websockets.exceptions import ConnectionClosed
from websockets.sync.server import serve

COMMANDS = {
    "move_left": "Mover a la izquierda",
    "move_right": "Mover a la derecha",
    "move_up": "Mover arriba",
    "move_down": "Mover abajo",
    "save_view": "Guardar encuadre",
    "restore_view": "Recuperar encuadre",
    "get_day_night": "Consultar modo día/noche",
    "set_day": "Activar modo Día",
    "set_night": "Activar modo Noche",
    "set_auto": "Activar modo Automático",
    "get_microphone": "Consultar micrófono",
    "mute_microphone": "Silenciar micrófono de la cámara",
    "unmute_microphone": "Reactivar micrófono de la cámara",
}


class CameraChannel:
    def __init__(self, token: str):
        if not token or not token.isascii() or not token.isprintable() or any(c.isspace() for c in token):
            raise ValueError("CAMERA_CONTROL_WS_TOKEN debe tener un token válido en backend/.env.")
        self._authorization = f"Bearer {token}".encode()
        self._changed = Condition()
        self._dispatch = Lock()
        self._connection = None
        self._closed = False
        self._pending = None
        self._result = None

    def authorize(self, connection, request):
        if request.path != "/camera":
            return connection.respond(HTTPStatus.NOT_FOUND, "Ruta no disponible.")
        if not self.accepts_token(request.headers.get_all("Authorization")):
            return connection.respond(HTTPStatus.UNAUTHORIZED, "Credencial inválida.")
        return None

    def accepts_token(self, headers: list[str]) -> bool:
        return len(headers) == 1 and compare_digest(headers[0].encode(), self._authorization)

    def handle(self, connection) -> None:
        peer_ip = connection.remote_address[0]
        with self._changed:
            occupied = self._closed or self._connection is not None
            if not occupied:
                self._connection = connection
                print(f"[WS] Controlador conectado desde {peer_ip} | activos: 1", flush=True)
                self._changed.notify_all()
        if occupied:
            connection.close(code=1008, reason="Ya hay un controlador conectado.")
            return
        try:
            for message in connection:
                self._receive(connection, message)
        except ConnectionClosed:
            pass
        finally:
            with self._changed:
                self._connection = None
                print(f"[WS] Controlador desconectado de {peer_ip} | activos: 0", flush=True)
                self._changed.notify_all()

    def _receive(self, connection, message: str | bytes) -> None:
        if not isinstance(message, str):
            return
        try:
            response = json.loads(message)
        except (ValueError, RecursionError):
            return
        if not isinstance(response, dict):
            return
        status = response.get("status")
        with self._changed:
            if (
                self._connection is connection
                and self._pending is not None
                and self._result is None
                and response.get("id") == self._pending
                and status in ("accepted", "rejected", "camera_error", "movement_limit")
            ):
                self._result = {"status": status}
                if status == "accepted":
                    state = response.get("state")
                    volume = response.get("volume")
                    if state in ("on", "off", "auto"):
                        self._result["state"] = state
                    if type(volume) is int and 0 <= volume <= 100:
                        self._result["volume"] = volume
                self._changed.notify_all()

    def send_command(self, action: str, timeout: float = 5) -> dict:
        if action not in COMMANDS:
            return {"status": "rejected"}
        if not self._dispatch.acquire(blocking=False):
            return {"status": "busy"}
        try:
            return self._send(action, timeout)
        finally:
            self._dispatch.release()

    def _send(self, action: str, timeout: float) -> dict:
        with self._changed:
            connection = self._connection
            if connection is None:
                return {"status": "offline"}
            command_id = uuid4().hex
            self._pending = command_id
            self._result = None
        try:
            connection.send(json.dumps({"id": command_id, "action": action}))
            with self._changed:
                self._changed.wait_for(
                    lambda: self._result is not None or self._connection is not connection,
                    timeout,
                )
                return self._result or {"status": "unconfirmed"}
        except (ConnectionClosed, OSError):
            return {"status": "unconfirmed"}
        finally:
            with self._changed:
                self._pending = None

    def wait_connected(self, timeout: float) -> bool:
        with self._changed:
            return self._changed.wait_for(lambda: self._connection is not None, timeout)

    def close(self) -> None:
        with self._changed:
            self._closed = True
            connection = self._connection
        if connection is not None:
            connection.close()


def local_server(channel: CameraChannel, port: int = 8765, *, host: str = "127.0.0.1"):
    return serve(
        channel.handle, host, port, process_request=channel.authorize,
        max_size=4096, open_timeout=5, close_timeout=2,
    )
