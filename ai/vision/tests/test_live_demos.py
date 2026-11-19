"""Pruebas del aviso y los controles de las demos ante un corte RTSP."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from scripts import phone_persistence_demo, preview_live
import live_preview
from rtsp.latest_frame import CaptureMetrics, FramePacket


class LiveDemoTests(unittest.TestCase):
    def test_both_demos_recover_and_can_close_during_an_outage(self):
        for demo in (preview_live, phone_persistence_demo):
            for close_with_x in (False, True):
                with self.subTest(demo=demo.__name__, close_with_x=close_with_x):
                    self.check_outage(demo, close_with_x)

    def check_outage(self, demo, close_with_x):
        first = FramePacket(np.ones((4, 4, 3), dtype=np.uint8), 1.0, 1)
        recovered = FramePacket(np.full_like(first.image, 2), 10.0, 2)
        capture = Mock()
        capture.metrics.return_value = CaptureMetrics(2, 25.0, 0, 1, True, 0.0)
        capture.read_latest.side_effect = [first, None, None, recovered, None]
        detector = Mock()
        detector.infer.return_value = SimpleNamespace(
            detections=(), device="CPU", inference_ms=1.0,
        )
        with (
            patch.object(demo, "RtspConfig"),
            patch.object(demo, "LatestFrameCapture", return_value=capture),
            patch.object(demo, "YoloDetector", return_value=detector),
            patch.object(demo, "cv2") as cv,
            patch.object(live_preview, "cv2", cv),
            patch.object(live_preview.time, "sleep"),
        ):
            cv.waitKey.side_effect = [-1] * 5 + [-1 if close_with_x else ord("q")]
            cv.getWindowProperty.side_effect = [1] * 5 + [0]
            demo.main()

        self.assertEqual(detector.infer.call_count, 2)
        shown = [call.args[1] for call in cv.imshow.call_args_list]
        self.assertEqual(len(shown), 5)
        self.assertIs(shown[0], shown[2])
        self.assertIs(shown[0], shown[4])
        np.testing.assert_array_equal(shown[1], first.image)
        np.testing.assert_array_equal(shown[3], recovered.image)
        capture.stop.assert_called_once()
        cv.destroyAllWindows.assert_called_once()
