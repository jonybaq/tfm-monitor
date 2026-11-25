"""Control ONVIF del filtro infrarrojo cuando el firmware lo ofrece."""

MODE_LABELS = {"ON": "Día", "OFF": "Noche", "AUTO": "Automático"}


class NightMode:
    def __init__(self, service, source_token: str):
        self._service = service
        self._source_token = source_token

    @classmethod
    def from_camera(cls, camera, source_token: str):
        return cls(camera.create_imaging_service(), source_token)

    def settings(self) -> tuple[str | None, tuple[str, ...]]:
        request = {"VideoSourceToken": self._source_token}
        current = self._service.GetImagingSettings(request)
        options = self._service.GetOptions(request)
        modes = getattr(options, "IrCutFilterModes", None) or ()
        supported = tuple(mode for mode in MODE_LABELS if mode in modes)
        return getattr(current, "IrCutFilter", None), supported

    def set_mode(self, mode: str) -> None:
        self._service.SetImagingSettings({
            "VideoSourceToken": self._source_token,
            "ImagingSettings": {"IrCutFilter": mode},
            "ForcePersistence": True,
        })
