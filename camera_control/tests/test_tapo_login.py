import contextlib
import io
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from camera_control.tapo_login import connect_tapo
from camera_control.tapo_controls import PRESET_NAME, run_tapo_menu


class TapoLoginTests(unittest.TestCase):
    def test_menu_moves_saves_restores_and_changes_mode(self):
        camera = Mock()
        previous = {"6": PRESET_NAME}
        updated = {**previous, "7": f"{PRESET_NAME} 1"}
        camera.getPresets.side_effect = [previous, updated, updated]
        camera.getDayNightMode.side_effect = ["auto", "on"]
        choose_action = Mock(side_effect=[0, 1, 2, 3, 4, 5, 6, 1, 7])
        with contextlib.redirect_stdout(io.StringIO()) as output:
            run_tapo_menu(camera, choose_action)
        self.assertEqual(
            [call.args for call in camera.moveMotor.call_args_list],
            [(-5, 0), (5, 0), (0, 5), (0, -5)],
        )
        camera.savePreset.assert_called_once_with(f"{PRESET_NAME} 1")
        camera.deletePreset.assert_called_once_with("6")
        camera.setPreset.assert_called_once_with("7")
        camera.setDayNightMode.assert_called_once_with("on")
        self.assertIn("Modo confirmado: Noche", output.getvalue())

    def test_saves_only_after_login_and_reuses_credentials(self):
        tapo = Mock(side_effect=[RuntimeError(), object(), object()])
        with TemporaryDirectory() as directory, patch.dict(
            sys.modules, {"pytapo": SimpleNamespace(Tapo=tapo)}
        ), contextlib.redirect_stdout(io.StringIO()):
            env_file = Path(directory) / ".env"
            with patch("builtins.input", side_effect=["", "example=key", "", "example=key"]):
                self.assertIsNone(connect_tapo("camera.local", env_file))
                self.assertFalse(env_file.exists())
                self.assertIsNotNone(connect_tapo("camera.local", env_file))
            with patch("builtins.input", side_effect=AssertionError):
                self.assertIsNotNone(connect_tapo("camera.local", env_file))
            tapo.assert_called_with(
                "camera.local", "admin", "example=key",
                cloudPassword="example=key", retryStok=False, printWarnInformation=False,
            )
