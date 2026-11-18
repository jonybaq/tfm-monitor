"""Pruebas de latest-frame sin cámara física."""

import time
import unittest

import numpy as np

from rtsp.latest_frame import LatestFrameCapture


class FakeCapture:
    def __init__(self, frames):
        self._frames = iter(frames)
        self.released = False

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


class LatestFrameCaptureTests(unittest.TestCase):
    def test_returns_latest_frame_and_metrics(self) -> None:
        frames = [np.full((2, 2, 3), value, dtype=np.uint8) for value in (1, 2)]
        capture = LatestFrameCapture(
            "rtsp://example.invalid/stream1",
            reconnect_delay_seconds=1,
            capture_factory=lambda url, backend: FakeCapture(frames),
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
