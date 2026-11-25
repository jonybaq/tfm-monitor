from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from camera_control.__main__ import configure_night_mode
from camera_control.imaging import NightMode


class NightModeTests(unittest.TestCase):
    def test_reports_current_mode_and_only_known_modes_advertised_by_camera(self):
        camera = Mock()
        service = camera.create_imaging_service.return_value
        service.GetImagingSettings.return_value = SimpleNamespace(IrCutFilter="AUTO")
        service.GetOptions.return_value = SimpleNamespace(
            IrCutFilterModes=["AUTO", "OFF", "UNKNOWN"],
        )
        control = NightMode.from_camera(camera, "source")
        self.assertEqual(control.settings(), ("AUTO", ("OFF", "AUTO")))
        service.GetOptions.assert_called_once_with({"VideoSourceToken": "source"})

    def test_sets_only_the_filter_setting(self):
        service = Mock()
        NightMode(service, "source").set_mode("OFF")
        service.SetImagingSettings.assert_called_once_with({
            "VideoSourceToken": "source",
            "ImagingSettings": {"IrCutFilter": "OFF"},
            "ForcePersistence": True,
        })

    def test_hides_unavailable_modes_and_allows_return_without_change(self):
        controller = Mock()
        mode = controller.night_mode.return_value
        mode.settings.side_effect = [("AUTO", ()), ("AUTO", ("ON", "AUTO"))]
        with patch("camera_control.__main__.choose_action", return_value=2) as choose:
            with patch("builtins.print"):
                configure_night_mode(controller, OSError)
                choose.assert_not_called()
                configure_night_mode(controller, OSError)
        choose.assert_called_once_with(("Día", "Automático", "Volver"))
        mode.set_mode.assert_not_called()

    def test_writes_selected_mode(self):
        controller = Mock()
        mode = controller.night_mode.return_value
        mode.settings.return_value = ("AUTO", ("OFF", "AUTO"))
        with patch("camera_control.__main__.choose_action", return_value=0):
            with patch("builtins.print") as tell:
                configure_night_mode(controller, OSError)
        mode.set_mode.assert_called_once_with("OFF")
        self.assertIn("Modo solicitado: Noche", tell.call_args.args[0])

    def test_reports_connection_failure_without_printing_remote_details(self):
        controller = Mock()
        controller.night_mode.side_effect = OSError("detalle privado")
        with patch("builtins.print") as tell:
            configure_night_mode(controller, OSError)
        self.assertIn("No se pudo consultar", tell.call_args.args[0])
        self.assertNotIn("detalle privado", tell.call_args.args[0])
