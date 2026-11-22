"""Vista de diagnóstico para M1: muestra el último frame sin IA."""

from __future__ import annotations

import logging
from pathlib import Path
import sys
import time

import cv2
import numpy as np

# Permite ejecutar el archivo directamente desde un IDE, además de usar
# ``python -m capture.scripts.preview_rtsp`` desde la raíz del repositorio.
if __package__ in (None, ""):
    capture_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(capture_root))

from rtsp.config import RtspConfig
from rtsp.latest_frame import LatestFrameCapture


METRICS_LOG_INTERVAL_SECONDS = 5.0


def _show_packet(window_name, packet, metrics) -> float:
    frame = packet.image
    frame_age_ms = (time.monotonic() - packet.captured_at) * 1000
    status = "conectada" if metrics.connected else "desconectada"
    lines = (
        f"Captura: {metrics.capture_fps:.1f} FPS",
        f"Edad local del frame: {frame_age_ms:.0f} ms",
        f"Conexión: {status}",
        f"Errores: {metrics.read_failures} | Intentos: {metrics.connection_attempts}",
        f"Reconexiones exitosas: {metrics.reconnects}",
    )
    for index, line in enumerate(lines):
        cv2.putText(
            frame,
            line,
            (10, 30 + index * 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )
    cv2.imshow(window_name, frame)
    return frame_age_ms


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = RtspConfig.from_environment()
    capture = LatestFrameCapture(config.url)
    window_name = "Tapo C220 - RTSP M1"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    capture.start()
    last_metrics_log_at = 0.0
    displayed_sequence: int | None = None
    no_video = np.zeros((360, 640, 3), dtype=np.uint8)
    cv2.putText(
        no_video, "Sin video RTSP", (24, 60),
        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2,
    )

    try:
        cv2.imshow(window_name, no_video)
        while True:
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                break
            packet = capture.read_latest()
            if packet is None:
                if displayed_sequence is not None:
                    cv2.imshow(window_name, no_video)
                    displayed_sequence = None
                time.sleep(0.01)
                continue
            if packet.sequence == displayed_sequence:
                time.sleep(0.005)
                continue
            metrics = capture.metrics()
            frame_age_ms = _show_packet(window_name, packet, metrics)
            displayed_sequence = packet.sequence
            now = time.monotonic()
            if now - last_metrics_log_at >= METRICS_LOG_INTERVAL_SECONDS:
                logging.info(
                    "Métricas RTSP | fps=%.1f | edad_local_frame_ms=%.0f | "
                    "conectada=%s | frames=%d | errores=%d | intentos=%d | "
                    "reconexiones_exitosas=%d",
                    metrics.capture_fps,
                    frame_age_ms,
                    metrics.connected,
                    metrics.received_frames,
                    metrics.read_failures,
                    metrics.connection_attempts,
                    metrics.reconnects,
                )
                last_metrics_log_at = now
    finally:
        capture.stop()
        cv2.destroyAllWindows()
        logging.info("Métricas finales: %s", capture.metrics())


if __name__ == "__main__":
    main()
