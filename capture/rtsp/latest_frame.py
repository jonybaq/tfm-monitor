"""Captura RTSP asíncrona que mantiene solo el frame más reciente."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import threading
import time
from typing import Any, Callable, Protocol

import cv2
import numpy as np


LOGGER = logging.getLogger(__name__)
OPEN_TIMEOUT_MS = 3000
READ_TIMEOUT_MS = 2000


class VideoCaptureProtocol(Protocol):
    """Interfaz mínima de OpenCV usada por la captura."""

    def isOpened(self) -> bool: ...

    def read(self) -> tuple[bool, Any]: ...

    def release(self) -> None: ...

    def set(self, property_id: int, value: float) -> bool: ...


@dataclass(frozen=True)
class FramePacket:
    """Frame y el instante local en el que se recibió."""

    image: np.ndarray
    captured_at: float
    sequence: int


@dataclass(frozen=True)
class CaptureMetrics:
    """Instantánea de las métricas disponibles en la adquisición."""

    received_frames: int
    capture_fps: float
    read_failures: int
    reconnects: int
    connected: bool
    last_frame_age_seconds: float | None
    connection_attempts: int = 0


CaptureFactory = Callable[[str, int], VideoCaptureProtocol]


class LatestFrameCapture:
    """Lee RTSP en segundo plano y descarta frames antiguos.

    La reconexión se intenta tras errores de apertura o lectura. Quien consume
    los frames nunca bloquea esperando la red: recibe el último frame o ``None``.
    """

    def __init__(
        self,
        url: str,
        reconnect_delay_seconds: float = 2.0,
        capture_factory: CaptureFactory | None = None,
    ) -> None:
        if reconnect_delay_seconds < 0:
            raise ValueError("reconnect_delay_seconds no puede ser negativo.")
        self._url = url
        self._reconnect_delay_seconds = reconnect_delay_seconds
        self._capture_factory = capture_factory or self._open_cv_capture
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._latest_packet: FramePacket | None = None
        self._received_frames = 0
        self._capture_fps = 0.0
        self._fps_window_frames = 0
        self._fps_window_started_at: float | None = None
        self._read_failures = 0
        self._reconnects = 0
        self._connection_attempts = 0
        self._has_connected = False
        self._connected = False
        self._sequence = 0

    @staticmethod
    def _open_cv_capture(url: str, backend: int) -> VideoCaptureProtocol:
        return cv2.VideoCapture(
            url,
            backend,
            [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, OPEN_TIMEOUT_MS,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC, READ_TIMEOUT_MS,
            ],
        )

    def start(self) -> None:
        """Inicia el hilo de captura una sola vez."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="rtsp-latest-frame",
                daemon=True,
            )
            self._thread.start()

    def read_latest(self) -> FramePacket | None:
        """Devuelve una copia del último frame de la conexión vigente."""
        with self._lock:
            if self._stop_event.is_set() or self._latest_packet is None:
                return None
            packet = self._latest_packet
            return FramePacket(packet.image.copy(), packet.captured_at, packet.sequence)

    def metrics(self) -> CaptureMetrics:
        """Devuelve métricas de adquisición sin exponer la URL RTSP."""
        with self._lock:
            age = None
            if self._latest_packet is not None:
                age = time.monotonic() - self._latest_packet.captured_at
            return CaptureMetrics(
                received_frames=self._received_frames,
                capture_fps=self._capture_fps,
                read_failures=self._read_failures,
                reconnects=self._reconnects,
                connected=self._connected,
                last_frame_age_seconds=age,
                connection_attempts=self._connection_attempts,
            )

    def stop(self, timeout_seconds: float = 5.0) -> None:
        """Solicita parada y espera a que el hilo lector libere OpenCV."""
        with self._lock:
            self._stop_event.set()
            self._latest_packet = None
            thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout_seconds)
            if thread.is_alive():
                LOGGER.warning("El hilo RTSP sigue cerrándose tras el tiempo de espera.")

    def _run(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                self._connection_attempts += 1
            try:
                capture = self._capture_factory(self._url, cv2.CAP_FFMPEG)
            except cv2.error:
                if not self._stop_event.is_set():
                    self._register_failure("OpenCV no pudo crear la captura RTSP.")
            else:
                try:
                    if not self._stop_event.is_set():
                        self._read_stream(capture)
                finally:
                    with self._lock:
                        self._connected = False
                        self._latest_packet = None
                    capture.release()
            self._wait_before_reconnect()

    def _read_stream(self, capture: VideoCaptureProtocol) -> None:
        try:
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            opened = capture.isOpened()
            with self._lock:
                self._connected = opened
                if opened:
                    self._reconnects += int(self._has_connected)
                    self._has_connected = True
            if not opened:
                if not self._stop_event.is_set():
                    self._register_failure("No se pudo abrir el stream RTSP.")
                return
            LOGGER.info("Stream RTSP conectado.")
            while not self._stop_event.is_set():
                ok, frame = capture.read()
                if self._stop_event.is_set():
                    break
                if not ok or frame is None:
                    self._register_failure("Error al leer un frame RTSP.")
                    break
                now = time.monotonic()
                with self._lock:
                    if self._stop_event.is_set():
                        break
                    self._sequence += 1
                    self._received_frames += 1
                    self._update_capture_fps(now)
                    self._latest_packet = FramePacket(frame, now, self._sequence)

        except cv2.error:
            if not self._stop_event.is_set():
                self._register_failure("OpenCV interrumpió la captura RTSP.")

    def _register_failure(self, message: str) -> None:
        with self._lock:
            self._read_failures += 1
        LOGGER.warning(message)

    def _update_capture_fps(self, received_at: float) -> None:
        """Actualiza un FPS de captura calculado en ventanas de un segundo."""
        if self._fps_window_started_at is None:
            self._fps_window_started_at = received_at
        self._fps_window_frames += 1
        elapsed = received_at - self._fps_window_started_at
        if elapsed >= 1.0:
            self._capture_fps = self._fps_window_frames / elapsed
            self._fps_window_started_at = received_at
            self._fps_window_frames = 0

    def _wait_before_reconnect(self) -> None:
        self._stop_event.wait(self._reconnect_delay_seconds)
