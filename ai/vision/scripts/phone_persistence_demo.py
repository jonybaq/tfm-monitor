"""Demo integrada: YOLO detecta celular y el motor temporal mide persistencia."""

from pathlib import Path
import sys
import time

import cv2

VISION_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
for path in (VISION_ROOT, PROJECT_ROOT / "ai" / "temporal", PROJECT_ROOT / "capture"):
    sys.path.insert(0, str(path))

from detector import YoloDetector
from engine import TemporalStateEngine
from temporal_models import SignalObservation
from rtsp.config import RtspConfig
from rtsp.latest_frame import LatestFrameCapture


PHONE_SIGNAL_NAME = "cell_phone_visible"
REMOTE_SIGNAL_NAME = "remote_visible"
DEMO_THRESHOLD_SECONDS = 5.0


def main() -> None:
    capture = LatestFrameCapture(RtspConfig.from_environment().url)
    detector = YoloDetector()
    print(f"Dispositivo de inferencia: {detector.device_name}")
    temporal = TemporalStateEngine({
        PHONE_SIGNAL_NAME: DEMO_THRESHOLD_SECONDS,
        REMOTE_SIGNAL_NAME: DEMO_THRESHOLD_SECONDS,
    })
    capture.start()
    last_sequence = 0
    try:
        while True:
            packet = capture.read_latest()
            if packet is None or packet.sequence == last_sequence:
                time.sleep(0.005)
                continue
            last_sequence = packet.sequence
            result = detector.infer(packet.image, packet.captured_at)
            phone_detections = [
                item for item in result.detections if item.class_name == "cell phone"
            ]
            remote_detections = [
                item for item in result.detections if item.class_name == "remote"
            ]
            visible = bool(phone_detections)
            phone_state = temporal.update(
                SignalObservation(PHONE_SIGNAL_NAME, visible, packet.captured_at)
            )
            remote_state = temporal.update(
                SignalObservation(REMOTE_SIGNAL_NAME, bool(remote_detections), packet.captured_at)
            )
            phone_duration = phone_state.duration_seconds if phone_state and phone_state.active else 0.0
            remote_duration = remote_state.duration_seconds if remote_state and remote_state.active else 0.0
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
            if phone_state and phone_state.persistence_reached:
                cv2.putText(frame, "CELULAR: UMBRAL ALCANZADO", (10, 120),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
            if remote_state and remote_state.persistence_reached:
                cv2.putText(frame, "CONTROL REMOTO: UMBRAL ALCANZADO", (10, 150),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.imshow("M3 - Persistencia de celular", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        capture.stop()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
