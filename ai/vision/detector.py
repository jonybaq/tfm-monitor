"""Adaptador de Ultralytics YOLO para M2."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import torch
from ultralytics import YOLO

from models import BoundingBox, Detection, InferenceResult


class YoloDetector:
    """Ejecuta un modelo YOLO intercambiable sobre una imagen BGR de OpenCV."""

    def __init__(self, model_path: str = "yolo11n.pt", image_size: int = 640) -> None:
        self._model = YOLO(model_path)
        self._image_size = image_size
        self._device: int | str = 0 if torch.cuda.is_available() else "cpu"
        self._device_name = (
            torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU"
        )

    @property
    def device_name(self) -> str:
        return self._device_name

    def infer(self, image: np.ndarray, captured_at: float) -> InferenceResult:
        """Devuelve detecciones y mide solo el tiempo de inferencia YOLO."""
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        started_at = time.perf_counter()
        results = self._model.predict(
            source=image,
            imgsz=self._image_size,
            device=self._device,
            verbose=False,
        )
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        inference_ms = (time.perf_counter() - started_at) * 1000
        return InferenceResult(
            captured_at=captured_at,
            inference_ms=inference_ms,
            device=self._device_name,
            detections=_to_detections(results[0]),
        )


def _to_detections(result: Any) -> tuple[Detection, ...]:
    """Convierte la salida de Ultralytics a tipos independientes de su API."""
    if result.boxes is None:
        return ()
    names = result.names
    detections = []
    for box in result.boxes:
        class_id = int(box.cls.item())
        x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
        detections.append(
            Detection(
                class_id=class_id,
                class_name=str(names[class_id]),
                confidence=float(box.conf.item()),
                bounding_box=BoundingBox(x1, y1, x2, y2),
            )
        )
    return tuple(detections)

