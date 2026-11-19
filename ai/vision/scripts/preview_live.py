"""Diagnóstico M2: captura RTSP estable + inferencia YOLO en vivo."""

from __future__ import annotations

import logging
from pathlib import Path
import sys
import time

import cv2

VISION_ROOT = Path(__file__).resolve().parents[1]
CAPTURE_ROOT = Path(__file__).resolve().parents[3] / "capture"
for path in (VISION_ROOT, CAPTURE_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from detector import YoloDetector
from live_preview import preview_frames
from rtsp.config import RtspConfig
from rtsp.latest_frame import LatestFrameCapture


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    capture = LatestFrameCapture(RtspConfig.from_environment().url)
    detector = YoloDetector()
    window_name = "M2 - Tapo C220 + YOLO11n"
    capture.start()
    processing_started_at = time.monotonic()
    processed_frames = 0
    last_metrics_log_at = 0.0

    try:
        for packet in preview_frames(capture, window_name):
            result = detector.infer(packet.image, packet.captured_at)
            processed_frames += 1
            elapsed = time.monotonic() - processing_started_at
            processing_fps = processed_frames / elapsed if elapsed else 0.0
            frame = packet.image.copy()
            for detection in result.detections:
                box = detection.bounding_box
                start, end = (round(box.x1), round(box.y1)), (round(box.x2), round(box.y2))
                cv2.rectangle(frame, start, end, (0, 255, 0), 2)
                cv2.putText(
                    frame, f"{detection.class_name} {detection.confidence:.2f}",
                    (start[0], max(25, start[1] - 8)), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (0, 255, 0), 2,
                )
            cv2.putText(frame, f"{result.device} | inferencia {result.inference_ms:.1f} ms",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
            cv2.putText(frame, f"procesamiento {processing_fps:.1f} FPS | captura {capture.metrics().capture_fps:.1f} FPS",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)
            cv2.imshow(window_name, frame)
            now = time.monotonic()
            if now - last_metrics_log_at >= 5.0:
                metrics = capture.metrics()
                logging.info(
                    "Métricas M2 | inferencia_ms=%.1f | procesamiento_fps=%.1f | "
                    "captura_fps=%.1f | frames=%d | errores=%d",
                    result.inference_ms,
                    processing_fps,
                    metrics.capture_fps,
                    metrics.received_frames,
                    metrics.read_failures,
                )
                last_metrics_log_at = now
    finally:
        capture.stop()
        cv2.destroyAllWindows()
        logging.info("Métricas finales de captura: %s", capture.metrics())


if __name__ == "__main__":
    main()
