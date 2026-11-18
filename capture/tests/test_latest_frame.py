"""Pruebas de latest-frame sin cámara física."""

import threading
import time
import unittest
from unittest.mock import patch

import cv2
import numpy as np

from rtsp.latest_frame import LatestFrameCapture, OPEN_TIMEOUT_MS, READ_TIMEOUT_MS


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
    def test_returns_latest_frame_and_metrics(self) -> None:
        frames = [np.full((2, 2, 3), value, dtype=np.uint8) for value in (1, 2)]
        source = FakeCapture(frames)
        capture = LatestFrameCapture(
            "rtsp://example.invalid/stream1",
            reconnect_delay_seconds=1,
            capture_factory=lambda url, backend: source,
        )
        with self.assertLogs("rtsp.latest_frame", level="WARNING"):
            capture.start()
            deadline = time.monotonic() + 1
            packet = None
            while time.monotonic() < deadline:
                packet = capture.read_latest()
                if packet is not None and packet.sequence >= 2:
                    break
                time.sleep(0.01)
            capture.stop()

        self.assertIsNotNone(packet)
        self.assertEqual(packet.sequence, 2)
        self.assertTrue(np.all(packet.image == 2))
        self.assertGreaterEqual(capture.metrics().received_frames, 2)
        self.assertGreaterEqual(capture.metrics().capture_fps, 0)
        self.assertEqual(len(source.release_threads), 1)
        self.assertIsNot(source.release_threads[0], threading.current_thread())

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
