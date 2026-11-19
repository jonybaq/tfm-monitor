"""Demo integrada: YOLO detecta celular y el motor temporal mide persistencia."""

import argparse
import math
from pathlib import Path
import sys

import cv2

VISION_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
for path in (VISION_ROOT, PROJECT_ROOT / "ai" / "temporal", PROJECT_ROOT / "capture"):
    sys.path.insert(0, str(path))

from detector import YoloDetector
from live_preview import preview_frames
from engine import TemporalStateEngine
from temporal_models import SignalObservation
from rtsp.config import RtspConfig
from rtsp.latest_frame import LatestFrameCapture


PHONE_SIGNAL_NAME = "cell_phone_visible"
REMOTE_SIGNAL_NAME = "remote_visible"
DEMO_THRESHOLD_SECONDS = 5.0
DEMO_MISSING_TOLERANCE_SECONDS = 0.5


class DetectionTimer:
    """Pausa el reloj de la señal mientras falte una detección."""

    def __init__(self, name: str, temporal: TemporalStateEngine) -> None:
        self._name = name
        self._temporal = temporal
        self._last_seen: float | None = None
        self._evidence_time = 0.0
        self._duration = 0.0
        self._missing = False
        self._reported_at: float | None = None

    @property
    def seconds_since_report(self) -> float:
        if self._reported_at is None:
            return 0.0
        return self._duration - self._reported_at

    def update(self, visible: bool, timestamp: float) -> tuple[float, bool]:
        last_seen = self._last_seen
        if last_seen is not None and (self._missing or not visible):
            if timestamp - last_seen >= DEMO_MISSING_TOLERANCE_SECONDS:
                self._temporal.update(SignalObservation(self._name, False, timestamp))
                self._last_seen = last_seen = None
                self._duration = 0.0
                self._reported_at = None
        if not visible:
            self._missing = True
            return self._duration, self._reported_at is not None

        if last_seen is None:
            self._evidence_time = timestamp
        elif not self._missing:
            self._evidence_time += timestamp - last_seen
        self._last_seen = timestamp
        self._missing = False
        state = self._temporal.update(
            SignalObservation(self._name, True, self._evidence_time)
        )
        self._duration = state.duration_seconds
        if state.persistence_reached and self._reported_at is None:
            self._reported_at = self._duration
        return self._duration, state.persistence_reached


def main(reminder_seconds: float | None = None) -> None:
    if reminder_seconds is not None and (
        not math.isfinite(reminder_seconds) or reminder_seconds <= 0
    ):
        raise ValueError("El intervalo de recordatorios debe ser positivo y finito.")
    capture = LatestFrameCapture(RtspConfig.from_environment().url)
    detector = YoloDetector(model_path=str(VISION_ROOT / "yolo11s.pt"))
    print(f"Dispositivo de inferencia: {detector.device_name}")
    thresholds = {
        PHONE_SIGNAL_NAME: DEMO_THRESHOLD_SECONDS,
        REMOTE_SIGNAL_NAME: DEMO_THRESHOLD_SECONDS,
    }
    def new_timers() -> tuple[DetectionTimer, DetectionTimer]:
        temporal = TemporalStateEngine(thresholds)
        return (
            DetectionTimer(PHONE_SIGNAL_NAME, temporal),
            DetectionTimer(REMOTE_SIGNAL_NAME, temporal),
        )

    phone_timer, remote_timer = new_timers()
    reported_intervals: dict[str, int] = {}

    def reset_persistence() -> None:
        nonlocal phone_timer, remote_timer
        phone_timer, remote_timer = new_timers()
        reported_intervals.clear()

    def report(name: str, reached: bool, elapsed: float) -> None:
        if not reached:
            reported_intervals.pop(name, None)
            return
        interval = int(elapsed // reminder_seconds) if reminder_seconds else 0
        previous = reported_intervals.get(name)
        if previous is None:
            print(f"{name}: umbral alcanzado")
        elif interval > previous:
            print(f"{name}: umbral activo hace {elapsed:.1f} s")
        reported_intervals[name] = interval

    capture.start()
    window_name = "M3 - Persistencia de celular"
    try:
        for packet in preview_frames(
            capture, window_name, on_video_lost=reset_persistence,
        ):
            result = detector.infer(packet.image, packet.captured_at)
            phone_detections = [
                item for item in result.detections if item.class_name == "cell phone"
            ]
            remote_detections = [
                item for item in result.detections if item.class_name == "remote"
            ]
            phone_duration, phone_reached = phone_timer.update(
                bool(phone_detections), packet.captured_at
            )
            remote_duration, remote_reached = remote_timer.update(
                bool(remote_detections), packet.captured_at
            )
            report(PHONE_SIGNAL_NAME, phone_reached, phone_timer.seconds_since_report)
            report(REMOTE_SIGNAL_NAME, remote_reached, remote_timer.seconds_since_report)
            frame = packet.image.copy()
            for detection in phone_detections:
                box = detection.bounding_box
                start = (round(box.x1), round(box.y1))
                end = (round(box.x2), round(box.y2))
                cv2.rectangle(frame, start, end, (0, 255, 0), 2)
                cv2.putText(
                    frame, f"cell phone {detection.confidence:.2f}",
                    (start[0], max(25, start[1] - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2,
                )
            for detection in remote_detections:
                box = detection.bounding_box
                start = (round(box.x1), round(box.y1))
                end = (round(box.x2), round(box.y2))
                cv2.rectangle(frame, start, end, (255, 200, 0), 2)
                cv2.putText(
                    frame, f"remote {detection.confidence:.2f}",
                    (start[0], max(25, start[1] - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 200, 0), 2,
                )
            cv2.putText(frame, f"Dispositivo: {result.device}", (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
            cv2.putText(frame, f"Celular: {phone_duration:.1f} s / 5 s", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, f"Control remoto: {remote_duration:.1f} s / 5 s", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 200, 0), 2)
            if phone_reached:
                cv2.putText(frame, f"CELULAR: UMBRAL ALCANZADO | {phone_timer.seconds_since_report:.1f} s", (10, 120),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
            if remote_reached:
                cv2.putText(frame, f"CONTROL REMOTO: UMBRAL ALCANZADO | {remote_timer.seconds_since_report:.1f} s", (10, 150),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.imshow(window_name, frame)
    finally:
        capture.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reminder-seconds", type=float)
    main(parser.parse_args().reminder_seconds)
