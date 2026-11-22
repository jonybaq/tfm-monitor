"""Experimental RTSP sender using FFmpeg libraries in the Python process."""

from collections.abc import Callable
from fractions import Fraction
import logging
import threading
import time

from capture.rtsp.config import RtspConfig, RtspConfigurationError
from .camera import show_countdown
from .config import StreamDestination


LOGGER = logging.getLogger(__name__)
VIDEO_TIME_BASE = Fraction(1, 30)
AUDIO_RATE = 48000
AUDIO_TIME_BASE = Fraction(1, AUDIO_RATE)


def set_video_timestamp(packet, frame_index: int) -> None:
    """Apply the same 30 FPS timestamps as the command-line sender."""
    packet.time_base = VIDEO_TIME_BASE
    packet.pts = packet.dts = frame_index


def set_audio_timestamp(frame, sample_index: int) -> int:
    """Place an Opus input frame on the resampled audio clock."""
    frame.time_base = AUDIO_TIME_BASE
    frame.pts = sample_index
    return sample_index + frame.samples


def format_progress(
    frames: int, recent_frames: int, interval: float, payload_bytes: int,
) -> str:
    media_seconds = frames * float(VIDEO_TIME_BASE)
    fps = recent_frames / interval
    bitrate = payload_bytes * 8 / media_seconds / 1000
    return (
        f"frame={frames}  fps={fps:.1f}  out_time={media_seconds:.1f}s  "
        f"bitrate={bitrate:.0f}kbits/s"
    )


class PyAvSender:
    def __init__(self) -> None:
        try:
            import av
        except ImportError:
            raise ValueError(
                r"PyAV no está disponible. Ejecuta .\.venv\Scripts\python.exe -m pip install av."
            ) from None
        self.av = av
        # Network errors can include an authenticated URL.
        av.logging.set_level(av.logging.PANIC)

    def _open_camera(self, camera: RtspConfig, timeout: float, *, low_latency=False):
        options = {"rtsp_transport": "tcp"}
        if low_latency:
            options["fflags"] = "+nobuffer"
        return self.av.open(camera.url, options=options, timeout=(timeout, timeout))

    def probe(
        self, camera: RtspConfig, *, interactive: bool, label: str,
    ) -> bool:
        deadline = time.monotonic() + 60
        stopped = threading.Event()
        countdown = threading.Thread(
            target=show_countdown, args=(camera.host, deadline, stopped, label),
        )
        if interactive:
            countdown.start()
        try:
            while (remaining := deadline - time.monotonic()) > 0:
                try:
                    with self._open_camera(camera, min(5, remaining)) as source:
                        if source.streams.video and next(source.decode(video=0), None) is not None:
                            return True
                except self.av.error.HTTPUnauthorizedError:
                    raise RtspConfigurationError(
                        "La cámara rechazó las credenciales RTSP."
                    ) from None
                except self.av.error.FFmpegError:
                    pass
                time.sleep(max(0, min(2, deadline - time.monotonic())))
            return False
        finally:
            stopped.set()
            if interactive:
                countdown.join()

    def send(
        self, camera: RtspConfig, destination: StreamDestination, *,
        start_timeout: float, on_connected: Callable[[], None], interactive: bool,
    ) -> str:
        if destination.transport != "rtsp":
            raise ValueError("El modo experimental de PyAV requiere RTSP.")
        camera_opened = False
        published = False
        started = last_update = time.monotonic()
        frames = 0
        last_frames = 0
        payload_bytes = 0
        audio_samples = 0
        try:
            with self._open_camera(
                camera, min(start_timeout, 5),
                low_latency=destination.mode == "local" and destination.low_latency,
            ) as source:
                camera_opened = True
                if not source.streams.video or (destination.audio_enabled and not source.streams.audio):
                    raise ValueError("La cámara no entrega las pistas requeridas.")
                with self.av.open(
                    destination.url, mode="w", format="rtsp",
                    options={"rtsp_transport": "tcp"}, timeout=(min(start_timeout, 5), 5),
                ) as output:
                    video = source.streams.video[0]
                    video_out = output.add_stream_from_template(video)
                    streams = [video]
                    if destination.audio_enabled:
                        audio = source.streams.audio[0]
                        streams.append(audio)
                        audio_out = output.add_stream("libopus", rate=AUDIO_RATE)
                        audio_out.layout = "mono"
                        audio_out.bit_rate = 32000
                        resampler = self.av.audio.resampler.AudioResampler(
                            format="s16", layout="mono", rate=AUDIO_RATE,
                        )
                    output.start_encoding()
                    for packet in source.demux(streams):
                        now = time.monotonic()
                        if not published and now - started >= start_timeout:
                            break
                        if packet.stream == video:
                            if not packet.size:
                                continue
                            set_video_timestamp(packet, frames)
                            packet.stream = video_out
                            output.mux(packet)
                            payload_bytes += packet.size
                            frames += 1
                            if not published:
                                published = True
                                on_connected()
                                media = "vídeo y audio" if destination.audio_enabled else "vídeo"
                                LOGGER.info("Enviando %s (%s) con PyAV", media, destination.mode)
                            if interactive and now - last_update >= 1:
                                stats = format_progress(
                                    frames, frames - last_frames, now - last_update, payload_bytes,
                                )
                                print(f"\r{stats}\033[K", end="", flush=True)
                                last_update = now
                                last_frames = frames
                        else:
                            for frame in packet.decode():
                                frame.pts = None
                                for sample in resampler.resample(frame):
                                    audio_samples = set_audio_timestamp(sample, audio_samples)
                                    for encoded in audio_out.encode(sample):
                                        output.mux(encoded)
                                        payload_bytes += encoded.size
        except self.av.error.HTTPUnauthorizedError:
            target = "El receptor" if camera_opened else "La cámara"
            raise ValueError(f"{target} rechazó las credenciales RTSP.") from None
        except self.av.error.FFmpegError as error:
            # The exception message and filename may contain authenticated URLs.
            LOGGER.warning("PyAV interrumpió la conexión (código %d).", error.errno)
        finally:
            if published and interactive:
                print(flush=True)
        if published:
            return "Envío interrumpido. Volviendo a conectar"
        return destination.waiting_message if camera_opened else "Esperando conexión de la cámara"
