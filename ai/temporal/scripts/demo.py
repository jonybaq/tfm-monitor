"""Muestra una secuencia temporal sintética en consola."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import TemporalStateEngine
from temporal_models import SignalObservation


def main() -> None:
    engine = TemporalStateEngine()
    sequence = (
        SignalObservation("senal_demo", True, 0.0),
        SignalObservation("senal_demo", True, 1.0),
        SignalObservation("senal_demo", False, 3.0),
        SignalObservation("senal_demo", False, 4.0),
        SignalObservation("senal_demo", True, 5.0),
    )
    print("La señal False finaliza el estado inmediatamente.\n")
    for observation in sequence:
        state = engine.update(observation)
        print(f"Entrada: {observation}")
        print(f"Estado:  {state}\n")


if __name__ == "__main__":
    main()
