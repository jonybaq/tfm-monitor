"""Tipos de entrada y salida del motor temporal."""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SignalObservation:
    name: str
    active: bool
    timestamp: float
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class StateUpdate:
    name: str
    active: bool
    started_at: float
    last_evidence_at: float
    duration_seconds: float
    ended_at: float | None = None
    persistence_reached: bool = False
