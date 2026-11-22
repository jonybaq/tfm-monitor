"""Preparación y comprobación de la cámara antes del envío."""

from collections.abc import Callable
from getpass import getpass
import math
import os
from pathlib import Path
import re
import subprocess
import threading
import time

from capture.rtsp.config import (
    DEFAULT_ENV_FILE,
    MissingRtspConfiguration,
    RtspConfig,
    RtspConfigurationError,
    validate_rtsp_host,
)

from .ffmpeg_environment import ffmpeg_environment


def configure_camera(
    *, interactive: bool, env_file: Path = DEFAULT_ENV_FILE,
    before_prompt: Callable[[], None] | None = None,
) -> RtspConfig:
    try:
        return RtspConfig.from_environment(env_file)
    except MissingRtspConfiguration as error:
        if not interactive:
            raise
        if before_prompt is not None:
            before_prompt()
        print(error, flush=True)
        missing = error.keys

    values = {}
    labels = {
        "RTSP_HOST": "IP o nombre de la cámara: ",
        "RTSP_USERNAME": "Usuario RTSP: ",
        "RTSP_PASSWORD": "Contraseña RTSP: ",
    }
    for key in missing:
        read = getpass if key == "RTSP_PASSWORD" else input
        raw = read(labels[key])
        value = raw.strip()
        if not value or any(character in raw for character in "\r\n\x00"):
            raise RtspConfigurationError(f"{key} está vacío o no es válido.")
        if key == "RTSP_HOST":
            validate_rtsp_host(value)
        if key == "RTSP_PASSWORD" and raw != value:
            raise RtspConfigurationError("RTSP_PASSWORD tiene espacios en los extremos.")
        values[key] = value

    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    lines = [line for line in lines if line.partition("=")[0].strip() not in values]
    lines.extend(f"{key}={value}" for key, value in values.items())
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ.update(values)
    return RtspConfig.from_environment(env_file)


def show_countdown(
    host: str, deadline: float, stopped: threading.Event, label: str = "",
    message: str = "Esperando conexión desde",
) -> None:
    while not stopped.is_set():
        seconds = max(0, math.ceil(deadline - time.monotonic()))
        prefix = f"{label} · " if label else ""
        print(
            f"\r{prefix}{message} {host} · {seconds:02d} s restantes\033[K",
            end="", flush=True,
        )
        if seconds == 0 or stopped.wait(1):
            break


def wait_for_camera(
    executable: str, camera: RtspConfig, *, timeout: float = 60,
    interactive: bool = False, label: str = "",
) -> bool:
    command = [
        executable, "-hide_banner", "-nostdin", "-loglevel", "error",
        "-progress", "pipe:1", "-rtsp_transport", "tcp", "-timeout", "5000000",
        "-i", camera.url, "-map", "0:v:0", "-an", "-frames:v", "1",
        "-f", "null", "-",
    ]
    deadline = time.monotonic() + timeout
    if not interactive:
        print(f"Esperando conexión desde {camera.host} (hasta {timeout:g} segundos).", flush=True)
        return probe_until(command, deadline)

    stopped = threading.Event()
    countdown = threading.Thread(
        target=show_countdown, args=(camera.host, deadline, stopped, label), daemon=True
    )
    countdown.start()
    try:
        return probe_until(command, deadline)
    finally:
        stopped.set()
        countdown.join()
        if not label:
            print(flush=True)


def probe_until(command: list[str], deadline: float) -> bool:
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=min(8, remaining), check=False,
                env=ffmpeg_environment(),
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        except subprocess.TimeoutExpired:
            pass
        else:
            if result.returncode == 0 and any(
                re.fullmatch(r"frame=\s*1", line) for line in result.stdout.splitlines()
            ):
                return True
            if "401 Unauthorized" in result.stderr:
                raise RtspConfigurationError("La cámara rechazó las credenciales RTSP.")
        remaining = deadline - time.monotonic()
        if remaining > 0:
            time.sleep(min(2, remaining))
    return False
