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
        self._capture: VideoCaptureProtocol | None = None
        self._latest_packet: FramePacket | None = None
        self._received_frames = 0
        self._capture_fps = 0.0
        self._fps_window_frames = 0
        self._fps_window_started_at: float | None = None
        self._read_failures = 0
        self._reconnects = 0
        self._connected = False
        self._sequence = 0

    @staticmethod
    def _open_cv_capture(url: str, _: int) -> VideoCaptureProtocol:
        return cv2.VideoCapture(url, cv2.CAP_FFMPEG)

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
        """Devuelve una copia del último frame, si existe."""
        with self._lock:
            if self._latest_packet is None:
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
            )

    def stop(self, timeout_seconds: float = 5.0) -> None:
        """Solicita parada y libera el recurso de OpenCV."""
        self._stop_event.set()
        with self._lock:
            capture = self._capture
        if capture is not None:
            capture.release()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout_seconds)
        with self._lock:
            self._connected = False
            self._capture = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                capture = self._capture_factory(self._url, cv2.CAP_FFMPEG)
            except cv2.error:
                self._register_failure("OpenCV no pudo crear la captura RTSP.")
                self._wait_before_reconnect()
                continue
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            with self._lock:
                self._capture = capture
                self._connected = capture.isOpened()
                self._reconnects += 1

            if not capture.isOpened():
                self._register_failure("No se pudo abrir el stream RTSP.")
                capture.release()
                self._wait_before_reconnect()
                continue

            LOGGER.info("Stream RTSP conectado.")
            while not self._stop_event.is_set():
                try:
                    ok, frame = capture.read()
                except cv2.error:
                    if not self._stop_event.is_set():
                        self._register_failure("OpenCV interrumpió la lectura RTSP.")
                    break
                if not ok or frame is None:
                    if self._stop_event.is_set():
                        break
                    self._register_failure("Error al leer un frame RTSP.")
                    break
                now = time.monotonic()
                with self._lock:
                    self._sequence += 1
                    self._received_frames += 1
                    self._update_capture_fps(now)
                    self._latest_packet = FramePacket(frame, now, self._sequence)

            capture.release()
            with self._lock:
                self._connected = False
                self._capture = None
            self._wait_before_reconnect()

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
