"""Pruebas del aviso y los controles de las demos ante un corte RTSP."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from scripts import phone_persistence_demo, preview_live
import live_preview
from rtsp.latest_frame import CaptureMetrics, FramePacket


class DetectionTimerTests(unittest.TestCase):
    def setUp(self):
        temporal = phone_persistence_demo.TemporalStateEngine({"phone": 5.0})
        self.timer = phone_persistence_demo.DetectionTimer("phone", temporal)

    def test_short_loss_pauses_then_resumes_without_counting_gap(self):
        self.assertEqual(self.timer.update(True, 10.0), (0.0, False))
        self.assertEqual(self.timer.update(True, 14.75), (4.75, False))
        self.assertEqual(self.timer.update(False, 14.875), (4.75, False))
        self.assertEqual(self.timer.update(True, 15.0), (4.75, False))
        self.assertEqual(self.timer.update(True, 15.25), (5.0, True))
        self.assertEqual(self.timer.update(False, 15.375), (5.0, True))

    def test_exposes_elapsed_evidence_time_without_sending_reports(self):
        with patch("builtins.print") as report:
            for timestamp in (0.0, 5.0, 14.75):
                self.timer.update(True, timestamp)
            self.timer.update(False, 14.875)
            self.assertEqual(self.timer.seconds_since_report, 9.75)
            self.timer.update(True, 15.0)
            self.assertEqual(self.timer.seconds_since_report, 9.75)
            self.timer.update(True, 15.25)
            self.assertEqual(self.timer.seconds_since_report, 10.0)
            self.timer.update(True, 25.25)
            self.assertEqual(self.timer.seconds_since_report, 20.0)
            self.assertEqual(self.timer.update(False, 25.75), (0.0, False))
            self.assertEqual(self.timer.seconds_since_report, 0.0)
            report.assert_not_called()

    def test_loss_at_limit_resets_timer(self):
        self.timer.update(True, 10.0)
        self.timer.update(True, 12.0)
        self.assertEqual(self.timer.update(False, 12.25), (2.0, False))
        self.assertEqual(self.timer.update(False, 12.5), (0.0, False))
        self.assertEqual(self.timer.update(False, 12.75), (0.0, False))
        self.assertEqual(self.timer.update(True, 13.0), (0.0, False))

    def test_detection_returning_at_limit_starts_new_timer(self):
        self.timer.update(True, 10.0)
        self.timer.update(True, 12.0)
        self.timer.update(False, 12.25)
        self.assertEqual(self.timer.update(True, 12.5), (0.0, False))


class LiveDemoTests(unittest.TestCase):
    def test_phone_and_remote_restart_after_video_loss(self):
        demo = phone_persistence_demo
        frame = np.zeros((4, 4, 3), dtype=np.uint8)
        capture = Mock()
        capture.read_latest.side_effect = [
            FramePacket(frame, 1.0, 1),
            FramePacket(frame, 3.0, 2),
            None,
            None,
            FramePacket(frame, 10.0, 3),
            FramePacket(frame, 13.0, 4),
            FramePacket(frame, 15.0, 5),
        ]
        box = SimpleNamespace(x1=0, y1=0, x2=3, y2=3)
        detections = tuple(
            SimpleNamespace(class_name=name, confidence=0.9, bounding_box=box)
            for name in ("cell phone", "remote")
        )
        detector = Mock(device_name="CPU")
        detector.infer.return_value = SimpleNamespace(detections=detections, device="CPU")
        with (
            patch.object(demo, "RtspConfig"),
            patch.object(demo, "LatestFrameCapture", return_value=capture),
            patch.object(demo, "YoloDetector", return_value=detector),
            patch.object(demo, "cv2") as cv,
            patch.object(live_preview, "cv2", cv),
            patch.object(live_preview.time, "sleep"),
        ):
            cv.waitKey.side_effect = [-1] * 7 + [ord("q")]
            cv.getWindowProperty.return_value = 1
            demo.main()

        labels = [call.args[1] for call in cv.putText.call_args_list]
        for name, alert in (
            ("Celular", "CELULAR: UMBRAL ALCANZADO | 0.0 s"),
            ("Control remoto", "CONTROL REMOTO: UMBRAL ALCANZADO | 0.0 s"),
        ):
            self.assertEqual(
                [label for label in labels if label.startswith(f"{name}:")],
                [f"{name}: {duration:.1f} s / 5 s" for duration in (0, 2, 0, 3, 5)],
            )
            self.assertEqual(labels.count(alert), 1)
            self.assertGreater(labels.index(alert), labels.index(f"{name}: 5.0 s / 5 s"))

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
