from datetime import timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from capture.rtsp.config import RtspConfig
from camera_control.ptz import CameraController, CameraControlError, SUPERVISION_PRESET
from camera_control.__main__ import choose_action, main, run_menu


class CameraControllerTests(unittest.TestCase):
    def setUp(self):
        self.ptz = Mock()
        self.controller = CameraController(self.ptz, "profile")

    @patch("camera_control.ptz.time.sleep")
    def test_moves_in_each_direction_and_stops(self, sleep):
        for direction, velocity in (
            ("izquierda", (-0.35, 0)), ("derecha", (0.35, 0)),
            ("arriba", (0, 0.35)), ("abajo", (0, -0.35)),
        ):
            with self.subTest(direction=direction):
                self.ptz.reset_mock()
                self.controller.move(direction)
                self.ptz.ContinuousMove.assert_called_once_with({
                    "ProfileToken": "profile",
                    "Velocity": {"PanTilt": {"x": velocity[0], "y": velocity[1]}},
                    "Timeout": timedelta(seconds=1),
                })
                self.ptz.Stop.assert_called_once_with({
                    "ProfileToken": "profile", "PanTilt": True, "Zoom": False,
                })
        self.assertEqual(sleep.call_count, 4)

    @patch("camera_control.ptz.time.sleep", side_effect=KeyboardInterrupt)
    def test_interrupt_still_stops_movement(self, _sleep):
        with self.assertRaises(KeyboardInterrupt):
            self.controller.move("arriba")
        self.ptz.Stop.assert_called_once()

    def test_saves_new_preset_if_it_does_not_exist(self):
        self.ptz.GetPresets.return_value = None
        self.controller.save_view()
        self.ptz.SetPreset.assert_called_once_with({
            "ProfileToken": "profile", "PresetName": SUPERVISION_PRESET,
        })

    def test_updates_only_the_named_preset_and_can_restore_it(self):
        self.ptz.GetPresets.return_value = [
            SimpleNamespace(Name="Otra posición", token="other"),
            SimpleNamespace(Name=SUPERVISION_PRESET, token="saved"),
        ]
        self.controller.save_view()
        self.controller.restore_view()
        self.ptz.SetPreset.assert_called_once_with({
            "ProfileToken": "profile", "PresetName": SUPERVISION_PRESET,
            "PresetToken": "saved",
        })
        self.ptz.GotoPreset.assert_called_once_with({
            "ProfileToken": "profile", "PresetToken": "saved",
        })

    def test_cannot_restore_a_missing_preset(self):
        self.ptz.GetPresets.return_value = []
        with self.assertRaisesRegex(CameraControlError, "Primero guarda"):
            self.controller.restore_view()
        self.ptz.GotoPreset.assert_not_called()

    def test_menu_executes_only_selected_actions(self):
        controller = Mock()
        with patch("camera_control.__main__.choose_action", side_effect=[1, 4, 5, 6]):
            with patch("builtins.print"):
                run_menu(controller, OSError)
        controller.move.assert_called_once_with("derecha")
        controller.save_view.assert_called_once()
        controller.restore_view.assert_called_once()

    def test_main_rejects_noninteractive_terminal(self):
        with (
            patch("camera_control.__main__.sys.stdin.isatty", return_value=False),
            patch("builtins.print") as tell,
        ):
            self.assertEqual(main(), 1)
        self.assertIn("terminal interactiva", tell.call_args.args[0])

    def test_connect_selects_first_profile_with_ptz_and_uses_bounded_transport(self):
        camera_factory = Mock()
        transport_factory = Mock()
        camera = camera_factory.return_value
        camera.create_media_service.return_value.GetProfiles.return_value = [
            SimpleNamespace(PTZConfiguration=None, token="ignored"),
            SimpleNamespace(PTZConfiguration=object(), token="selected"),
        ]
        with patch.dict("sys.modules", {
            "onvif": SimpleNamespace(ONVIFCamera=camera_factory),
            "zeep.transports": SimpleNamespace(Transport=transport_factory),
        }):
            controller = CameraController.connect(RtspConfig("localhost", "user", "sample"))
        transport_factory.assert_called_once_with(timeout=5, operation_timeout=5)
        camera_factory.assert_called_once_with(
            "localhost", 2020, "user", "sample", transport=transport_factory.return_value,
        )
        self.assertIs(controller._ptz, camera.create_ptz_service.return_value)
        self.assertEqual(controller._profile_token, "selected")

    def test_keyboard_selection_wraps_and_accepts_enter(self):
        keyboard = SimpleNamespace(getwch=Mock(side_effect=["x", "\xe0", "H", "\r"]))
        with patch.dict("sys.modules", {"msvcrt": keyboard}), patch("builtins.print"):
            self.assertEqual(choose_action(("Arriba", "Salir")), 1)

    def test_main_runs_in_its_own_terminal(self):
        with (
            patch("camera_control.__main__.sys.platform", "win32"),
            patch("camera_control.__main__.sys.stdin.isatty", return_value=True),
            patch.dict("sys.modules", {"onvif.exceptions": SimpleNamespace(ONVIFError=OSError)}),
            patch("camera_control.__main__.RtspConfig.from_environment") as config,
            patch("camera_control.__main__.CameraController.connect") as connect,
            patch("camera_control.__main__.run_menu") as menu,
        ):
            self.assertEqual(main(), 0)
        connect.assert_called_once_with(config.return_value)
        menu.assert_called_once_with(connect.return_value, OSError)

    def test_menu_leaves_protocol_details_out_of_console(self):
        controller = Mock()
        controller.move.side_effect = OSError("detalle privado")
        with patch("camera_control.__main__.choose_action", side_effect=[0, 6]):
            with patch("builtins.print") as tell:
                run_menu(controller, OSError)
        text = tell.call_args.args[0]
        self.assertIn("no aceptó", text)
        self.assertNotIn("detalle privado", text)
