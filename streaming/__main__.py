"""Arranca y supervisa la publicación RTSP a SRT."""

from dataclasses import dataclass, field
from collections.abc import Callable
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time

from capture.rtsp.config import RtspConfig, RtspConfigurationError

from .camera import configure_camera, show_countdown, wait_for_camera
from .config import StreamDestination, choose_option
from .console import ConsoleStep, finish_group


LOGGER = logging.getLogger(__name__)
CAMERA_WAIT = "Esperando conexión de la cámara"
INTERRUPTED = "Envío interrumpido. Volviendo a conectar"
RETRY_SECONDS = 3
START_TIMEOUT = 20
STALL_TIMEOUT = 12
RECEIVER_TIMEOUT = 60
FFMPEG_CHECK = "1. Comprobando instalación de FFmpeg"
CAMERA_CONFIG_CHECK = "2.1 Verificando configuración RTSP"
CAMERA_VIDEO_CHECK = "2.2 Comprobando vídeo de la cámara"


def find_ffmpeg() -> str | None:
    executable = shutil.which("ffmpeg")
    if executable:
        return executable
    app_data = os.getenv("LOCALAPPDATA")
    if not app_data:
        return None
    winget = Path(app_data) / "Microsoft" / "WinGet"
    link = winget / "Links" / "ffmpeg.exe"
    if link.is_file():
        return str(link)
    candidates = (winget / "Packages").glob("Gyan.FFmpeg_*/ffmpeg-*/bin/ffmpeg.exe")
    return next((str(path) for path in sorted(candidates, reverse=True) if path.is_file()), None)


def prepare_ffmpeg(
    *, interactive: bool, before_prompt: Callable[[], None] | None = None
) -> str | None:
    executable = find_ffmpeg()
    if executable:
        return executable
    winget = shutil.which("winget")
    if not interactive or not winget:
        return None
    if before_prompt is not None:
        before_prompt()
    selected = choose_option(
        "FFmpeg no está disponible. ¿Deseas que lo instale por ti?",
        ("No", "Sí"),
    )
    if selected == 0:
        return None
    result = subprocess.run(
        [winget, "install", "--id", "Gyan.FFmpeg", "--exact"], check=False
    )
    if result.returncode == 0:
        return find_ffmpeg()
    LOGGER.error("WinGet no pudo instalar FFmpeg.")
    return None


def initialize_ffmpeg(*, interactive: bool) -> str | None:
    title = "Proceso de inicialización"
    print(f"\033[1m{title}\033[0m" if interactive else title, flush=True)
    step = ConsoleStep(FFMPEG_CHECK, interactive)
    step.start()
    try:
        executable = prepare_ffmpeg(interactive=interactive, before_prompt=step.pause)
    except (KeyboardInterrupt, EOFError, OSError):
        step.finish(False)
        raise
    step.finish(bool(executable))
    if not executable:
        print("Se necesita FFmpeg para establecer la conexión.", flush=True)
    return executable


def initialize_camera(executable: str, *, interactive: bool) -> RtspConfig | None:
    group = "2. Verificación de la cámara"
    print(group, flush=True)
    prompted = False
    config_step = ConsoleStep(CAMERA_CONFIG_CHECK, interactive)

    def before_prompt() -> None:
        nonlocal prompted
        prompted = True
        config_step.pause()

    config_step.start()
    try:
        camera = configure_camera(interactive=interactive, before_prompt=before_prompt)
    except (RtspConfigurationError, OSError, EOFError) as error:
        config_step.finish(False)
        finish_group(group, False, interactive, 0 if prompted else 2)
        if isinstance(error, RtspConfigurationError):
            print(error, flush=True)
        print("Revisa la configuración RTSP en capture/.env.", flush=True)
        return None
    except KeyboardInterrupt:
        config_step.finish(False)
        finish_group(group, False, interactive, 0 if prompted else 2)
        raise
    config_step.finish(True)

    video_step = ConsoleStep(CAMERA_VIDEO_CHECK, interactive)
    video_step.start(animate=False)
    try:
        received = wait_for_camera(
            executable, camera, interactive=interactive, label="2.2 Vídeo"
        )
    except RtspConfigurationError as error:
        video_step.finish(False)
        finish_group(group, False, interactive, 0 if prompted else 3)
        print(f"{error} Corrige capture/.env y vuelve a iniciar.", flush=True)
        return None
    except (KeyboardInterrupt, OSError):
        video_step.finish(False)
        finish_group(group, False, interactive, 0 if prompted else 3)
        raise
    video_step.finish(received)
    finish_group(group, received, interactive, 0 if prompted else 3)
    if not received:
        print(
            "Se necesita la cámara encendida y enviando vídeo. "
            "Verifica la conexión y corrige capture/.env si corresponde.",
            flush=True,
        )
        return None
    return camera


def ffmpeg_command(
    executable: str, camera: RtspConfig, destination: StreamDestination
) -> list[str]:
    command = [
        executable, "-hide_banner", "-nostdin", "-nostats", "-loglevel", "info",
        "-progress", "pipe:2", "-rtsp_transport", "tcp", "-timeout", "5000000",
    ]
    local_rtsp = destination.mode == "local" and destination.transport == "rtsp"
    if destination.low_latency and local_rtsp:
        command.extend(["-fflags", "+nobuffer"])
    command.extend([
        "-i", camera.url, "-map", "0:v:0", "-c:v", "copy",
        "-bsf:v", "setts=pts=N/(30*TB):dts=N/(30*TB)",
    ])
    if destination.audio_enabled:
        command.extend([
            "-map", "0:a:0", "-c:a", "libopus", "-ar", "48000",
            "-ac", "1", "-b:a", "32k",
        ])
    else:
        command.append("-an")
    if destination.transport == "rtsp":
        return command + ["-f", "rtsp", "-rtsp_transport", "tcp", destination.url]
    return command + ["-f", "mpegts", destination.url]


@dataclass
class Attempt:
    camera_opened: bool = False
    output_opened: bool = False
    frames: int = 0
    last_progress: float | None = None
    issue: str = ""
    progress_fields: dict[str, str] = field(default_factory=dict)
    stats: str = ""

    def read(self, line: str, now: float) -> None:
        key, separator, value = line.strip().partition("=")
        if separator and key in {"frame", "fps", "bitrate", "out_time", "speed"}:
            self.progress_fields[key] = value.strip()
        if key == "progress" and value in {"continue", "end"}:
            self.stats = "  ".join(
                f"{name}={self.progress_fields[name]}"
                for name in ("frame", "fps", "out_time", "bitrate", "speed")
                if name in self.progress_fields
            )
        elif line.startswith("Input #0, rtsp,"):
            self.camera_opened = True
        elif line.startswith(("Output #0, mpegts,", "Output #0, rtsp,")):
            self.output_opened = True
        elif line.startswith("frame="):
            value = line.partition("=")[2].strip()
            if value.isdecimal() and int(value) > self.frames:
                self.frames = int(value)
                self.last_progress = now

        if "matches no streams" in line:
            self.issue = "La cámara no entrega las pistas requeridas."
        elif "401 Unauthorized" in line:
            self.issue = (
                "El receptor rechazó las credenciales de publicación RTSP."
                if self.camera_opened else "La cámara rechazó las credenciales RTSP."
            )
        elif "Unknown encoder" in line or "Bitstream filter not found" in line:
            self.issue = "La instalación de FFmpeg no admite el flujo configurado."


def read_progress(process: subprocess.Popen[str], attempt: Attempt) -> None:
    # FFmpeg puede incluir credenciales en stderr. Solo publicamos estados propios.
    assert process.stderr is not None
    for line in process.stderr:
        attempt.read(line, time.monotonic())


def publish_once(
    command: list[str], destination: StreamDestination, *,
    start_timeout: float = START_TIMEOUT,
    on_connected: Callable[[], None] | None = None,
    interactive: bool = False,
) -> str:
    with subprocess.Popen(
        command, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    ) as process:
        attempt = Attempt()
        reader = threading.Thread(
            target=read_progress, args=(process, attempt), daemon=True
        )
        started = time.monotonic()
        announced = False
        displayed_stats = ""
        try:
            reader.start()
            while process.poll() is None:
                last_progress = attempt.last_progress
                if last_progress is not None:
                    if not announced:
                        if on_connected is not None:
                            on_connected()
                        media = "vídeo y audio" if destination.audio_enabled else "vídeo"
                        LOGGER.info("Enviando %s (%s)", media, destination.mode)
                        announced = True
                    stats = attempt.stats
                    if interactive and stats and stats != displayed_stats:
                        print(f"\r{stats}\033[K", end="", flush=True)
                        displayed_stats = stats
                    if time.monotonic() - last_progress >= STALL_TIMEOUT:
                        break
                elif time.monotonic() - started >= start_timeout:
                    break
                time.sleep(0.2)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if reader.ident is not None:
                reader.join(timeout=2)
            if displayed_stats:
                print(flush=True)

    if attempt.issue:
        raise ValueError(attempt.issue)
    if attempt.output_opened:
        return INTERRUPTED
    if attempt.camera_opened:
        return destination.waiting_message
    return CAMERA_WAIT


def publish(
    command: list[str], destination: StreamDestination, *, interactive: bool
) -> int:
    mode = "Local" if destination.mode == "local" else "Azure"
    ConsoleStep(f"3. Destino elegido · {mode}", interactive).finish(True)
    protocol = destination.transport.upper()
    ConsoleStep(f"4. Tipo de transmisión elegido · {protocol}", interactive).finish(True)
    label = f"5. Validando conexión · {mode} por {protocol}"
    address = f"{destination.host}:{destination.port}"
    step = ConsoleStep(label, interactive)
    deadline = time.monotonic() + RECEIVER_TIMEOUT
    stopped = threading.Event()
    countdown = None
    if interactive:
        countdown = threading.Thread(
            target=show_countdown,
            args=(address, deadline, stopped, "", f"5. Validando {mode} por {protocol}"),
            daemon=True,
        )
        countdown.start()
    else:
        print(f"{label} · {address} · hasta {RECEIVER_TIMEOUT} s", flush=True)

    connected = False

    def finish_check(success: bool) -> None:
        stopped.set()
        if countdown is not None:
            countdown.join()
        step.finish(success)

    def confirm_connection() -> None:
        nonlocal connected
        if not connected:
            connected = True
            finish_check(True)

    previous = ""
    try:
        while True:
            remaining = deadline - time.monotonic()
            if not connected and remaining <= 0:
                finish_check(False)
                LOGGER.error(
                    "%s. Revisa que %s esté en ejecución y verifica streaming/.env.",
                    destination.waiting_message, address,
                )
                return 1
            message = publish_once(
                command, destination,
                start_timeout=START_TIMEOUT if connected else min(START_TIMEOUT, remaining),
                on_connected=confirm_connection,
                interactive=interactive,
            )
            if connected and (message != previous or message == INTERRUPTED):
                LOGGER.warning(message)
                previous = message
            pause = RETRY_SECONDS if connected else max(
                0, min(RETRY_SECONDS, deadline - time.monotonic())
            )
            time.sleep(pause)
    except (KeyboardInterrupt, ValueError, OSError):
        if not connected:
            finish_check(False)
        raise
    finally:
        stopped.set()
        if countdown is not None:
            countdown.join()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        interactive = sys.stdin.isatty()
        executable = initialize_ffmpeg(interactive=interactive)
        if executable is None:
            return 1
        camera = initialize_camera(executable, interactive=interactive)
        if camera is None:
            return 1
        destination = StreamDestination.from_environment(interactive=interactive)
        command = ffmpeg_command(executable, camera, destination)
        return publish(command, destination, interactive=interactive)
    except KeyboardInterrupt:
        LOGGER.info("Envío detenido")
        return 0
    except EOFError:
        LOGGER.error("No se pudo leer el destino. Configura STREAMING_MODE.")
    except ValueError as error:
        LOGGER.error("%s", error)
    except OSError:
        LOGGER.error("No se pudo leer la configuración o ejecutar FFmpeg.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
