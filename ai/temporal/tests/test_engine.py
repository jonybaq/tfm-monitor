import unittest

from engine import TemporalStateEngine
from temporal_models import SignalObservation


class TemporalStateEngineTests(unittest.TestCase):
    def test_accumulates_duration_and_ends_when_signal_becomes_inactive(self):
        engine = TemporalStateEngine()
        started = engine.update(SignalObservation("signal_test", True, 0.0))
        active = engine.update(SignalObservation("signal_test", True, 1.0))
        ended = engine.update(SignalObservation("signal_test", False, 3.0))

        self.assertTrue(started.active)
        self.assertEqual(active.duration_seconds, 1.0)
        self.assertFalse(ended.active)
        self.assertEqual(ended.duration_seconds, 3.0)

    def test_rejects_out_of_order_timestamps(self):
        engine = TemporalStateEngine()
        engine.update(SignalObservation("signal_test", True, 2.0))

        with self.assertRaises(ValueError):
            engine.update(SignalObservation("signal_test", True, 1.0))

    def test_does_not_reach_persistence_before_threshold(self):
        engine = TemporalStateEngine({"signal_test": 5.0})
        engine.update(SignalObservation("signal_test", True, 0.0))
        update = engine.update(SignalObservation("signal_test", True, 3.0))

        self.assertFalse(update.persistence_reached)

    def test_reaches_persistence_at_threshold(self):
        engine = TemporalStateEngine({"signal_test": 5.0})
        engine.update(SignalObservation("signal_test", True, 0.0))
        update = engine.update(SignalObservation("signal_test", True, 5.0))

        self.assertTrue(update.persistence_reached)

    def test_restarts_duration_after_signal_ends(self):
        engine = TemporalStateEngine({"signal_test": 5.0})
        engine.update(SignalObservation("signal_test", True, 0.0))
        engine.update(SignalObservation("signal_test", False, 2.0))
        update = engine.update(SignalObservation("signal_test", True, 3.0))

        self.assertEqual(update.duration_seconds, 0.0)
        self.assertFalse(update.persistence_reached)

    def test_uses_independent_thresholds_per_signal(self):
        engine = TemporalStateEngine({"phone": 5.0, "remote": 3.0})
        engine.update(SignalObservation("phone", True, 0.0))
        engine.update(SignalObservation("remote", True, 0.0))
        phone = engine.update(SignalObservation("phone", True, 3.0))
        remote = engine.update(SignalObservation("remote", True, 3.0))

        self.assertFalse(phone.persistence_reached)
        self.assertTrue(remote.persistence_reached)
