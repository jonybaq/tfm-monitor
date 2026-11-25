from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from camera_control.__main__ import choose_action, main


class CameraControlCliTests(unittest.TestCase):
    def test_keyboard_selection_wraps_and_accepts_enter(self):
        keyboard = SimpleNamespace(getwch=Mock(side_effect=["x", "\xe0", "H", "\r"]))
        with patch.dict("sys.modules", {"msvcrt": keyboard}), patch("builtins.print"):
            self.assertEqual(choose_action(("Arriba", "Salir")), 1)

    def test_keyboard_down_skips_unrelated_extended_keys(self):
        keyboard = SimpleNamespace(getwch=Mock(
            side_effect=["\xe0", "K", "\x00", "P", "\r"],
        ))
        with patch.dict("sys.modules", {"msvcrt": keyboard}), patch("builtins.print"):
            self.assertEqual(choose_action(("Arriba", "Abajo", "Salir")), 1)

    def test_escape_and_control_c_cancel_keyboard_selection(self):
        for key in ("\x1b", "\x03"):
            keyboard = SimpleNamespace(getwch=Mock(return_value=key))
            with (
                self.subTest(key=key),
                patch.dict("sys.modules", {"msvcrt": keyboard}),
                patch("builtins.print"),
                self.assertRaises(KeyboardInterrupt),
            ):
                choose_action(("Arriba", "Salir"))

    def test_main_connects_directly_with_pytapo(self):
        with (
            patch("camera_control.__main__.sys.platform", "win32"),
            patch("camera_control.__main__.sys.stdin.isatty", return_value=True),
            patch("camera_control.__main__.RtspConfig.from_environment",
                  return_value=SimpleNamespace(host="camera.local")),
            patch("camera_control.__main__.connect_tapo") as connect,
            patch("camera_control.__main__.run_tapo_menu") as run_menu,
        ):
            self.assertEqual(main(), 0)
        connect.assert_called_once_with("camera.local")
        run_menu.assert_called_once_with(connect.return_value, choose_action)
