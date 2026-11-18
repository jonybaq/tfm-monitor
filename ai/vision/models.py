"""Tipos estructurados producidos por el pipeline visual."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BoundingBox:
    """Caja delimitadora en píxeles: izquierda, arriba, derecha, abajo."""

    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class Detection:
    class_id: int
    class_name: str
    confidence: float
    bounding_box: BoundingBox


@dataclass(frozen=True)
class InferenceResult:
    captured_at: float
    inference_ms: float
    device: str
    detections: tuple[Detection, ...]

