"""Experimental RTSP sender using FFmpeg libraries in the Python process."""

from collections.abc import Callable
from fractions import Fraction
import logging
import threading
import time

from capture.rtsp.config import RtspConfig, RtspConfigurationError
from .camera import show_countdown
from .config import StreamDestination, StreamingError


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


class PublicationProgress:
    def __init__(self) -> None:
        self.frames = 0
        self.payload_bytes = 0
        self.last_frames = 0
        self.last_update = time.monotonic()

    def record_video(self, size: int, interactive: bool) -> None:
        self.frames += 1
        self.payload_bytes += size
        now = time.monotonic()
        interval = now - self.last_update
        if interactive and interval >= 1:
            stats = format_progress(
                self.frames, self.frames - self.last_frames, interval, self.payload_bytes,
            )
            print(f"\r{stats}\033[K", end="", flush=True)
            self.last_update = now
            self.last_frames = self.frames


class OpusTrack:
    def __init__(self, av, output) -> None:
        self.stream = output.add_stream("libopus", rate=AUDIO_RATE)
        self.stream.layout = "mono"
        self.stream.bit_rate = 32000
        self.resampler = av.audio.resampler.AudioResampler(
            format="s16", layout="mono", rate=AUDIO_RATE,
        )
        self.sample_index = 0

    def forward(self, packet, output) -> int:
        payload_bytes = 0
        for frame in packet.decode():
            frame.pts = None
            for sample in self.resampler.resample(frame):
                self.sample_index = set_audio_timestamp(sample, self.sample_index)
                for encoded in self.stream.encode(sample):
                    output.mux(encoded)
                    payload_bytes += encoded.size
        return payload_bytes


class PyAvSender:
    def __init__(self) -> None:
        try:
            import av
        except ImportError:
            raise StreamingError(
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
            raise StreamingError("El modo experimental de PyAV requiere RTSP.")
        camera_opened = False
        progress = PublicationProgress()
        started = time.monotonic()
        try:
            with self._open_camera(
                camera, min(start_timeout, 5),
                low_latency=destination.mode == "local" and destination.low_latency,
            ) as source:
                camera_opened = True
                if not source.streams.video or (destination.audio_enabled and not source.streams.audio):
                    raise StreamingError("La cámara no entrega las pistas requeridas.")
                with self.av.open(
                    destination.url, mode="w", format="rtsp",
                    options={"rtsp_transport": "tcp"}, timeout=(min(start_timeout, 5), 5),
                ) as output:
                    self._publish_packets(
                        source, output, destination, started + start_timeout,
                        on_connected, interactive, progress,
                    )
        except self.av.error.HTTPUnauthorizedError:
            target = "El receptor" if camera_opened else "La cámara"
            raise StreamingError(f"{target} rechazó las credenciales RTSP.") from None
        except self.av.error.FFmpegError as error:
            # The exception message and filename may contain authenticated URLs.
            LOGGER.warning("PyAV interrumpió la conexión (código %d).", error.errno)
        finally:
            if progress.frames and interactive:
                print(flush=True)
        if progress.frames:
            return "Envío interrumpido. Volviendo a conectar"
        return destination.waiting_message if camera_opened else "Esperando conexión de la cámara"

    def _publish_packets(
        self, source, output, destination: StreamDestination, deadline: float,
        on_connected: Callable[[], None], interactive: bool,
        progress: PublicationProgress,
    ) -> None:
        video = source.streams.video[0]
        video_out = output.add_stream_from_template(video)
        streams = [video]
        audio = None
        if destination.audio_enabled:
            streams.append(source.streams.audio[0])
            audio = OpusTrack(self.av, output)
        output.start_encoding()
        for packet in source.demux(streams):
            if not progress.frames and time.monotonic() >= deadline:
                return
            if packet.stream != video:
                if audio is not None:
                    progress.payload_bytes += audio.forward(packet, output)
                continue
            if not packet.size:
                continue
            set_video_timestamp(packet, progress.frames)
            packet.stream = video_out
            output.mux(packet)
            progress.record_video(packet.size, interactive)
            if progress.frames == 1:
                self._report_connected(destination, on_connected)

    def _report_connected(
        self, destination: StreamDestination, on_connected: Callable[[], None],
    ) -> None:
        on_connected()
        media = "vídeo y audio" if destination.audio_enabled else "vídeo"
        LOGGER.info("Enviando %s (%s) con PyAV", media, destination.mode)
