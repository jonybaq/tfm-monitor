"""Pruebas de la vista RTSP sin cámara ni ventana física."""

import unittest
from unittest.mock import Mock, patch

import numpy as np

from rtsp.latest_frame import CaptureMetrics, FramePacket
from scripts import preview_rtsp


class PreviewRtspTests(unittest.TestCase):
    def test_draws_only_new_frames_and_disconnect_transition(self):
        first = FramePacket(np.zeros((4, 4, 3), dtype=np.uint8), 1.0, 1)
        second = FramePacket(np.ones_like(first.image), 2.0, 2)
        capture = Mock()
        capture.read_latest.side_effect = [None, first, first, None, None, second]
        capture.metrics.return_value = CaptureMetrics(2, 25.0, 0, 0, True, 0.0)

        with (
            patch.object(preview_rtsp, "RtspConfig"),
            patch.object(preview_rtsp, "LatestFrameCapture", return_value=capture),
            patch.object(preview_rtsp, "cv2") as cv,
            patch.object(preview_rtsp.time, "sleep"),
        ):
            cv.waitKey.side_effect = [-1] * 6 + [ord("q")]
            cv.getWindowProperty.return_value = 1
            preview_rtsp.main()

        shown = [call.args[1] for call in cv.imshow.call_args_list]
        self.assertEqual(len(shown), 4)
        self.assertIs(shown[0], shown[2])
        self.assertIs(shown[1], first.image)
        self.assertIs(shown[3], second.image)
        capture.stop.assert_called_once()
        cv.destroyAllWindows.assert_called_once()
