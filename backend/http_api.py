"""Local HTTP interface for the camera control channel."""

import json
from hmac import compare_digest
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .camera_socket import COMMANDS, CameraChannel

QUERIES = {
    "/api/v1/camera/day-night": "get_day_night",
    "/api/v1/camera/microphone": "get_microphone",
}
STATUS_CODES = {
    "accepted": HTTPStatus.OK,
    "rejected": HTTPStatus.BAD_REQUEST,
    "camera_error": HTTPStatus.BAD_GATEWAY,
    "movement_limit": HTTPStatus.CONFLICT,
    "unconfirmed": HTTPStatus.GATEWAY_TIMEOUT,
    "offline": HTTPStatus.SERVICE_UNAVAILABLE,
    "busy": HTTPStatus.CONFLICT,
}


def create_http_server(channel: CameraChannel, credential: str, port: int = 8080):
    if not credential or not credential.isascii() or not credential.isalnum():
        raise ValueError("Configura CAMERA_CONTROL_API_TOKEN en backend/.env con un valor alfanumérico.")
    expected = f"Bearer {credential}".encode()

    class CameraRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._dispatch(QUERIES.get(self.path))

        def do_POST(self):
            prefix = "/api/v1/camera/actions/"
            action = self.path[len(prefix):] if self.path.startswith(prefix) else ""
            self._dispatch(action if action in COMMANDS and action not in QUERIES.values() else None)

        def _dispatch(self, action: str | None):
            values = self.headers.get_all("Authorization", [])
            matches = len(values) == 1 and compare_digest(values[0].encode(), expected)
            endpoint = self.path if action is not None else "(ruta desconocida)"
            print(f"[API] {self.command} {endpoint} | origen: {self.client_address[0]}", flush=True)
            if not matches:
                print("[API] HTTP 401 | Sin envío por WebSocket", flush=True)
                self._respond(HTTPStatus.UNAUTHORIZED, {"status": "unauthorized"})
            elif action is None:
                print("[API] HTTP 404 | Sin envío por WebSocket", flush=True)
                self._respond(HTTPStatus.NOT_FOUND, {"status": "not_found"})
            else:
                result = channel.send_command(action)
                status = STATUS_CODES[result["status"]]
                print(f"[API] HTTP {status.value} | Resultado del canal WebSocket: {json.dumps(result)}", flush=True)
                self._respond(status, result)

        def _respond(self, status: HTTPStatus, payload: dict):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            if status == HTTPStatus.UNAUTHORIZED:
                self.send_header("WWW-Authenticate", "Bearer")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            # Do not log raw client paths or headers.
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), CameraRequestHandler)
