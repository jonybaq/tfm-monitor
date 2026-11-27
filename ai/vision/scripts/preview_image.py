"""Ejecuta YOLO sobre una imagen pública o una ruta local y muestra resultados."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import requests

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detector import YoloDetector

DEFAULT_SOURCE = "https://ultralytics.com/images/bus.jpg"


def load_image(source: str) -> np.ndarray:
    """Carga una imagen BGR local o la muestra oficial."""
    if source == DEFAULT_SOURCE:
        with requests.get(DEFAULT_SOURCE, timeout=15) as response:
            response.raise_for_status()
            data = np.frombuffer(response.content, dtype=np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    else:
        if "://" in source:
            raise ValueError("Usa una ruta local o la imagen de ejemplo.")
        image = cv2.imread(source)
    if image is None:
        raise ValueError("No se pudo cargar la imagen indicada.")
    return image


def draw_detections(image: np.ndarray, result) -> np.ndarray:
    annotated = image.copy()
    for detection in result.detections:
        box = detection.bounding_box
        start = (round(box.x1), round(box.y1))
        end = (round(box.x2), round(box.y2))
        label = f"{detection.class_name} {detection.confidence:.2f}"
        cv2.rectangle(annotated, start, end, (0, 255, 0), 2)
        cv2.putText(
            annotated, label, (start[0], max(25, start[1] - 8)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
        )
    return annotated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Ruta a una imagen local")
    arguments = parser.parse_args()
    image = load_image(arguments.source)
    detector = YoloDetector()
    detector.infer(image, time.monotonic())  # Warm-up; no se mide como resultado.
    result = detector.infer(image, time.monotonic())
    annotated = draw_detections(image, result)
    cv2.putText(
        annotated, f"{result.device} | {result.inference_ms:.1f} ms",
        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2,
    )
    cv2.imshow("M2 - YOLO detections", annotated)
    print(f"Detecciones: {len(result.detections)}")
    for detection in result.detections:
        print(f"{detection.class_name}: {detection.confidence:.2f}")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

