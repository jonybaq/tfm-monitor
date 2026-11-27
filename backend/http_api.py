"""FastAPI interface for the camera control channel."""

from functools import partial
from hmac import compare_digest
from http import HTTPStatus

from anyio import from_thread, to_thread
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

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


class CameraWebSocket:
    """Adapt an ASGI socket to the existing synchronous camera channel."""

    def __init__(self, socket: WebSocket):
        self.socket = socket
        self.remote_address = socket.client or ("desconocido", 0)

    def __iter__(self):
        while (event := from_thread.run(self.socket.receive))["type"] != "websocket.disconnect":
            yield event.get("text") or event.get("bytes", b"")

    def send(self, message: str) -> None:
        try:
            from_thread.run(self.socket.send_text, message)
        except (WebSocketDisconnect, RuntimeError) as error:
            raise OSError("WebSocket disconnected") from error

    def close(self, code: int = 1000, reason: str = "") -> None:
        from_thread.run(partial(self.socket.close, code=code, reason=reason))


def create_app(channel: CameraChannel, credential: str) -> FastAPI:
    if not credential or not credential.isascii() or not credential.isalnum():
        raise ValueError("Configura CAMERA_CONTROL_API_TOKEN en backend/.env con un valor alfanumérico.")
    expected = f"Bearer {credential}".encode()
    app = FastAPI(title="TFM - Control de cámara", version="1.0")

    def dispatch(request: Request, action: str | None) -> JSONResponse:
        values = request.headers.getlist("authorization")
        endpoint = request.url.path if action is not None else "(ruta desconocida)"
        peer = request.client.host if request.client else "desconocido"
        print(f"[API] {request.method} {endpoint} | origen: {peer}", flush=True)
        headers = {"Cache-Control": "no-store"}
        if len(values) != 1 or not compare_digest(values[0].encode(), expected):
            print("[API] HTTP 401 | Sin envío por WebSocket", flush=True)
            headers["WWW-Authenticate"] = "Bearer"
            return JSONResponse({"status": "unauthorized"}, status_code=401, headers=headers)
        if action is None:
            print("[API] HTTP 404 | Sin envío por WebSocket", flush=True)
            return JSONResponse({"status": "not_found"}, status_code=404, headers=headers)
        result = channel.send_command(action)
        status = STATUS_CODES[result["status"]]
        print(f"[API] HTTP {status.value} | Resultado del canal WebSocket: {result}", flush=True)
        return JSONResponse(result, status_code=status.value, headers=headers)

    @app.get("/api/v1/camera/day-night")
    def day_night(request: Request):
        return dispatch(request, "get_day_night")

    @app.get("/api/v1/camera/microphone")
    def microphone(request: Request):
        return dispatch(request, "get_microphone")

    @app.post("/api/v1/camera/actions/{action}")
    def command(request: Request, action: str):
        allowed = action in COMMANDS and action not in QUERIES.values()
        return dispatch(request, action if allowed else None)

    @app.websocket("/camera")
    async def controller(socket: WebSocket):
        if not channel.accepts_token(socket.headers.getlist("authorization")):
            await socket.close(code=1008)
            return
        await socket.accept()
        await to_thread.run_sync(channel.handle, CameraWebSocket(socket))

    return app
