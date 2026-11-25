import contextlib
import io
import sys
import unittest
from getpass import GetPassWarning
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from camera_control.tapo_controls import PRESET_NAME, run_tapo_menu
from camera_control.tapo_login import connect_tapo


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
        tapo = Mock(side_effect=[Exception(), object(), object()])
        with TemporaryDirectory() as directory, patch.dict(
            sys.modules, {"pytapo": SimpleNamespace(Tapo=tapo)}
        ), contextlib.redirect_stdout(io.StringIO()):
            config_directory = Path(directory) / "camera_control"
            config_directory.mkdir()
            env_file = config_directory / ".env"
            other_file = Path(directory) / "another.env"
            with patch("camera_control.tapo_login.ENV_FILE", env_file):
                env_file.write_text("TAPO_CONTROL_USERNAME=admin\nENV_FILE=another.env\n")
                with (
                    patch("builtins.input", return_value=""),
                    patch("camera_control.tapo_login.getpass", return_value="../another.env"),
                ):
                    self.assertIsNone(connect_tapo("camera.local"))
                    self.assertNotIn("TAPO_CLOUD_PASSWORD", env_file.read_text())
                    self.assertIsNotNone(connect_tapo("camera.local"))
                self.assertFalse(other_file.exists())
                self.assertIn("TAPO_CLOUD_PASSWORD=../another.env", env_file.read_text())
                with (
                    patch("builtins.input", side_effect=AssertionError),
                    patch("camera_control.tapo_login.getpass", side_effect=AssertionError),
                ):
                    self.assertIsNotNone(connect_tapo("camera.local"))
            tapo.assert_called_with(
                "camera.local", "admin", "../another.env",
                cloudPassword="../another.env", retryStok=False, printWarnInformation=False,
            )

    def test_stops_when_the_terminal_cannot_hide_password_input(self):
        tapo = Mock()
        with (
            TemporaryDirectory() as directory,
            patch.dict(sys.modules, {"pytapo": SimpleNamespace(Tapo=tapo)}),
            patch("camera_control.tapo_login.ENV_FILE", Path(directory) / ".env"),
            patch("builtins.input", return_value=""),
            patch("camera_control.tapo_login.getpass", side_effect=GetPassWarning),
            contextlib.redirect_stdout(io.StringIO()),
        ):
            self.assertIsNone(connect_tapo("camera.local"))
        tapo.assert_not_called()
