"""Movimiento y recuperación del encuadre mediante ONVIF."""

from datetime import timedelta
import time

from capture.rtsp.config import RtspConfig
from .imaging import NightMode

ONVIF_PORT = 2020
SUPERVISION_PRESET = "TFM - Encuadre de supervision"
MOVE_SECONDS = 0.35
VELOCITY = 0.35
DIRECTIONS = {
    "izquierda": (-VELOCITY, 0),
    "derecha": (VELOCITY, 0),
    "arriba": (0, VELOCITY),
    "abajo": (0, -VELOCITY),
}


class CameraControlError(RuntimeError):
    """Error de control que se puede mostrar al operador."""


class CameraController:
    def __init__(self, ptz, profile_token: str, *, night_mode_factory=None):
        self._ptz = ptz
        self._profile_token = profile_token
        self._night_mode_factory = night_mode_factory

    @classmethod
    def connect(cls, config: RtspConfig, port: int = ONVIF_PORT):
        try:
            from onvif import ONVIFCamera
            from zeep.transports import Transport
        except ImportError:
            raise CameraControlError(
                "Instala las dependencias de camera_control/requirements.txt."
            ) from None

        camera = ONVIFCamera(
            config.host, port, config.username, config.password,
            transport=Transport(timeout=5, operation_timeout=5),
        )
        media = camera.create_media_service()
        profile = next(
            (item for item in media.GetProfiles() if item.PTZConfiguration is not None), None,
        )
        if profile is None:
            raise CameraControlError("La cámara no devolvió un perfil con control PTZ.")
        source = getattr(profile, "VideoSourceConfiguration", None)
        night_mode = (
            lambda: NightMode.from_camera(camera, source.SourceToken)
        ) if source is not None else None
        return cls(camera.create_ptz_service(), profile.token, night_mode_factory=night_mode)

    def night_mode(self) -> NightMode:
        if self._night_mode_factory is None:
            raise CameraControlError("El perfil no ofrece una fuente de vídeo para consultar el modo nocturno.")
        return self._night_mode_factory()

    def move(self, direction: str) -> None:
        x, y = DIRECTIONS[direction]
        try:
            self._ptz.ContinuousMove({
                "ProfileToken": self._profile_token,
                "Velocity": {"PanTilt": {"x": x, "y": y}},
                "Timeout": timedelta(seconds=1),
            })
            time.sleep(MOVE_SECONDS)
        finally:
            self._ptz.Stop({
                "ProfileToken": self._profile_token, "PanTilt": True, "Zoom": False,
            })

    def _preset_token(self) -> str | None:
        for preset in self._ptz.GetPresets({"ProfileToken": self._profile_token}) or ():
            if preset.Name == SUPERVISION_PRESET:
                return preset.token
        return None

    def save_view(self) -> None:
        request = {"ProfileToken": self._profile_token, "PresetName": SUPERVISION_PRESET}
        token = self._preset_token()
        if token is not None:
            request["PresetToken"] = token
        self._ptz.SetPreset(request)

    def restore_view(self) -> None:
        token = self._preset_token()
        if token is None:
            raise CameraControlError("Primero guarda un encuadre de supervisión.")
        self._ptz.GotoPreset({"ProfileToken": self._profile_token, "PresetToken": token})
