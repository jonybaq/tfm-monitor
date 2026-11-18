"""Pruebas de latest-frame sin cámara física."""

import threading
import time
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from rtsp.latest_frame import LatestFrameCapture, OPEN_TIMEOUT_MS, READ_TIMEOUT_MS
from rtsp.config import RtspConfig


class FakeCapture:
    def __init__(self, frames):
        self._frames = iter(frames)
        self.released = False
        self.release_threads = []

    def isOpened(self):
        return True

    def set(self, property_id, value):
        return True

    def read(self):
        if self.released:
            return False, None
        try:
            return True, next(self._frames)
        except StopIteration:
            return False, None

    def release(self):
        self.released = True
        self.release_threads.append(threading.current_thread())


class LatestFrameCaptureTests(unittest.TestCase):
    def test_open_exception_keeps_credentials_out_of_application_log(self):
        config = RtspConfig("127.0.0.1", "usuario_ficticio", "clave_ficticia")
        retry_wait = threading.Event()

        def fail_open(url, backend):
            raise cv2.error(f"Simulated failure opening {url}")

        capture = LatestFrameCapture(config.url, capture_factory=fail_open)

        def wait_before_reconnect():
            retry_wait.set()
            capture._stop_event.wait(timeout=5)

        with patch.object(capture, "_wait_before_reconnect", side_effect=wait_before_reconnect):
            with self.assertLogs("rtsp.latest_frame", level="WARNING") as logs:
                capture.start()
                try:
                    self.assertTrue(retry_wait.wait(timeout=2))
                finally:
                    capture.stop()

        output = "\n".join(logs.output)
        self.assertIn("OpenCV no pudo crear la captura RTSP.", output)
        self.assertNotIn(config.username, output)
        self.assertNotIn(config.password, output)

    def test_returns_latest_frame_and_metrics(self) -> None:
        frames = [np.full((2, 2, 3), value, dtype=np.uint8) for value in (1, 2)]
        source = FakeCapture(frames)
        capture = LatestFrameCapture(
            "rtsp://example.invalid/stream1",
            reconnect_delay_seconds=1,
            capture_factory=lambda url, backend: source,
        )
        finish_read = threading.Event()

        def read_frame():
            ok, frame = FakeCapture.read(source)
            if not ok:
                finish_read.wait(timeout=5)
            return ok, frame

        with patch.object(source, "read", side_effect=read_frame):
            capture.start()
            try:
                packet = self.wait_for_packet(capture, 2)
            finally:
                capture.stop(timeout_seconds=0)
                finish_read.set()
                capture.stop()

        self.assertIsNotNone(packet)
        self.assertEqual(packet.sequence, 2)
        self.assertTrue(np.all(packet.image == 2))
        self.assertGreaterEqual(capture.metrics().received_frames, 2)
        self.assertGreaterEqual(capture.metrics().capture_fps, 0)
        self.assertEqual(len(source.release_threads), 1)
        self.assertIsNot(source.release_threads[0], threading.current_thread())
        self.assertIsNone(capture.read_latest())

    def wait_for_packet(self, capture, minimum_sequence):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            packet = capture.read_latest()
            if packet is not None and packet.sequence >= minimum_sequence:
                return packet
            time.sleep(0.01)
        self.fail("No llegó un fotograma de la secuencia esperada.")

    def test_invalidates_frame_on_disconnect_and_recovers_with_new_frame(self):
        disconnect = threading.Event()
        reconnecting = threading.Event()
        resume = threading.Event()
        stopped = threading.Event()
        old_frame = np.zeros((2, 2, 3), dtype=np.uint8)
        new_frame = np.ones_like(old_frame)
        first = FakeCapture([old_frame])
        second = FakeCapture([new_frame])

        def read_first():
            ok, frame = FakeCapture.read(first)
            if not ok:
                disconnect.wait(timeout=5)
            return ok, frame

        def read_second():
            ok, frame = FakeCapture.read(second)
            if not ok:
                stopped.wait(timeout=5)
            return ok, frame

        def reopen():
            reconnecting.set()
            resume.wait(timeout=5)
            return second

        with (
            patch.object(first, "read", side_effect=read_first),
            patch.object(second, "read", side_effect=read_second),
            self.assertLogs("rtsp.latest_frame", level="WARNING"),
        ):
            sources = iter((lambda: first, reopen))
            capture = LatestFrameCapture(
                "rtsp://example.invalid", 0, lambda *_: next(sources)(),
            )
            capture.start()
            try:
                original = self.wait_for_packet(capture, 1)
                disconnect.set()
                self.assertTrue(reconnecting.wait(timeout=2))
                self.assertIsNone(capture.read_latest())
                self.assertFalse(capture.metrics().connected)
                resume.set()
                recovered = self.wait_for_packet(capture, original.sequence + 1)
                np.testing.assert_array_equal(recovered.image, new_frame)
            finally:
                capture.stop(timeout_seconds=0)
                disconnect.set()
                resume.set()
                stopped.set()
                capture.stop()
        self.assertIsNone(capture.read_latest())

    def test_stop_during_read_leaves_release_to_reader(self):
        reading = threading.Event()
        finish_read = threading.Event()
        source = FakeCapture([])
        reader_threads = []

        def blocking_read():
            reader_threads.append(threading.current_thread())
            reading.set()
            finish_read.wait(timeout=5)
            raise cv2.error("Lectura simulada interrumpida")

        with patch.object(source, "read", side_effect=blocking_read):
            capture = LatestFrameCapture("rtsp://example.invalid", capture_factory=lambda *_: source)
            capture.start()
            try:
                self.assertTrue(reading.wait(timeout=2))
                with self.assertLogs("rtsp.latest_frame", level="WARNING"):
                    capture.stop(timeout_seconds=0)
                self.assertFalse(source.released)
            finally:
                finish_read.set()
                capture.stop()
        self.assertEqual(source.release_threads, reader_threads)
        self.assertFalse(capture.metrics().connected)
        self.assertEqual(capture.metrics().read_failures, 0)

    def test_opencv_receives_open_and_read_timeouts(self):
        with patch("rtsp.latest_frame.cv2.VideoCapture") as open_capture:
            LatestFrameCapture._open_cv_capture("rtsp://example.invalid", cv2.CAP_FFMPEG)
        open_capture.assert_called_once_with(
            "rtsp://example.invalid",
            cv2.CAP_FFMPEG,
            [
                cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, OPEN_TIMEOUT_MS,
                cv2.CAP_PROP_READ_TIMEOUT_MSEC, READ_TIMEOUT_MS,
            ],
        )
