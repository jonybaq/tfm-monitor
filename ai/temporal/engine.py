"""Persistencia temporal genérica, independiente de IA, UI y alertas."""

from __future__ import annotations

from dataclasses import dataclass

from temporal_models import SignalObservation, StateUpdate


@dataclass
class _ActiveState:
    started_at: float
    last_evidence_at: float


class TemporalStateEngine:
    """Mantiene duración de estados a partir de señales activas/inactivas."""

    def __init__(self, persistence_thresholds: dict[str, float] | None = None) -> None:
        self._persistence_thresholds = persistence_thresholds or {}
        if any(value < 0 for value in self._persistence_thresholds.values()):
            raise ValueError("Los umbrales de persistencia no pueden ser negativos.")
        self._states: dict[str, _ActiveState] = {}
        self._last_timestamps: dict[str, float] = {}

    def update(self, observation: SignalObservation) -> StateUpdate | None:
        """Actualiza el estado de una señal y devuelve un cambio observable."""
        self._validate_timestamp(observation)
        state = self._states.get(observation.name)
        if observation.active:
            if state is None:
                state = _ActiveState(observation.timestamp, observation.timestamp)
                self._states[observation.name] = state
            else:
                state.last_evidence_at = observation.timestamp
            return self._snapshot(observation.name, state, observation.timestamp)

        if state is None:
            return None
        del self._states[observation.name]
        return StateUpdate(
            name=observation.name,
            active=False,
            started_at=state.started_at,
            last_evidence_at=state.last_evidence_at,
            duration_seconds=observation.timestamp - state.started_at,
            ended_at=observation.timestamp,
        )

    def _validate_timestamp(self, observation: SignalObservation) -> None:
        previous = self._last_timestamps.get(observation.name)
        if previous is not None and observation.timestamp < previous:
            raise ValueError("Los timestamps de una señal deben ser crecientes.")
        self._last_timestamps[observation.name] = observation.timestamp

    def _snapshot(self, name: str, state: _ActiveState, timestamp: float) -> StateUpdate:
        duration = timestamp - state.started_at
        threshold = self._persistence_thresholds.get(name)
        return StateUpdate(
            name=name,
            active=True,
            started_at=state.started_at,
            last_evidence_at=state.last_evidence_at,
            duration_seconds=duration,
            persistence_reached=threshold is not None and duration >= threshold,
        )
