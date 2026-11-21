"""Configuración de la conexión RTSP obtenida del entorno."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
from urllib.parse import quote

DEFAULT_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class RtspConfigurationError(ValueError):
    """Indica que faltan o son inválidos los valores de conexión RTSP."""


class MissingRtspConfiguration(RtspConfigurationError):
    """Expone los nombres de las variables obligatorias que faltan."""

    def __init__(self, keys: list[str]) -> None:
        self.keys = keys
        super().__init__("Faltan variables de entorno requeridas: " + ", ".join(keys))


@dataclass(frozen=True)
class RtspConfig:
    """Configuración RTSP con credenciales excluidas de su representación."""

    host: str
    username: str = field(repr=False)
    password: str = field(repr=False)
    port: int = 554
    stream_path: str = "stream1"

    @property
    def url(self) -> str:
        """Construye una URL que contiene credenciales y debe mantenerse privada."""
        username = quote(self.username, safe="")
        password = quote(self.password, safe="")
        path = self.stream_path.lstrip("/")
        return f"rtsp://{username}:{password}@{self.host}:{self.port}/{path}"

    @classmethod
    def from_environment(cls, env_file: Path | None = None) -> "RtspConfig":
        """Lee RTSP_* del entorno y, opcionalmente, de un archivo local `.env`.

        Las variables ya presentes en el entorno tienen prioridad. El archivo
        `capture/.env` es local, no se registra y debe permanecer fuera de Git.
        """
        if env_file is None:
            env_file = DEFAULT_ENV_FILE
        _load_environment_file(env_file)
        required = {
            "RTSP_HOST": os.getenv("RTSP_HOST", "").strip(),
            "RTSP_USERNAME": os.getenv("RTSP_USERNAME", "").strip(),
            "RTSP_PASSWORD": os.getenv("RTSP_PASSWORD", ""),
        }
        missing = [name for name, value in required.items() if not value]
        port_text = os.getenv("RTSP_PORT", "554")
        try:
            port = int(port_text)
        except ValueError as error:
            raise RtspConfigurationError("RTSP_PORT debe ser un entero.") from error
        if not 1 <= port <= 65535:
            raise RtspConfigurationError("RTSP_PORT debe estar entre 1 y 65535.")

        stream_path = os.getenv("RTSP_STREAM_PATH", "stream1").strip()
        if not stream_path:
            raise RtspConfigurationError("RTSP_STREAM_PATH no puede estar vacío.")
        if missing:
            raise MissingRtspConfiguration(missing)

        return cls(
            host=required["RTSP_HOST"],
            username=required["RTSP_USERNAME"],
            password=required["RTSP_PASSWORD"],
            port=port,
            stream_path=stream_path,
        )


def _load_environment_file(env_file: Path) -> None:
    """Carga asignaciones simples `CLAVE=VALOR` sin sobrescribir el entorno."""
    if not env_file.is_file():
        return

    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", maxsplit=1)
        key = key.strip()
        if key.startswith("RTSP_") and key not in os.environ:
            os.environ[key] = value.strip()
