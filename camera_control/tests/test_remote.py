import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import Mock, patch

from websockets.sync.server import serve

from camera_control.remote import command_result, run_remote, run_remote_from_config


class RemoteControlTests(unittest.TestCase):
    def test_reports_limit_with_direction_and_a_distinct_status(self):
        camera = Mock()
        camera.moveMotor.side_effect = [
            {"error_code": -64304},
            Exception('Error: motor blocked, Response: {"error_code": -64304}'),
        ]
        with redirect_stdout(StringIO()) as output:
            for _ in range(2):
                self.assertEqual(
                    command_result(camera, '{"id":"1","action":"move_left"}'),
                    {"id": "1", "status": "movement_limit"},
                )
        self.assertIn("La cámara ya no puede moverse más hacia la izquierda.", output.getvalue())

    def test_retry_menu_can_continue_and_return(self):
        choose = Mock(side_effect=[1, 0])
        with (
            patch("camera_control.remote.read_settings", return_value={}),
            patch("camera_control.remote.run_remote", side_effect=OSError) as run,
            patch("camera_control.remote.sleep") as delay,
            redirect_stdout(StringIO()),
        ):
            run_remote_from_config(Mock(), choose)
        self.assertEqual(run.call_count, 8)
        self.assertEqual(delay.call_count, 6)
        self.assertEqual(choose.call_count, 2)
        choose.assert_called_with(("Volver al menú principal", "Seguir reintentando"))

    def test_receives_move_over_websocket_and_returns_result(self):
        camera = Mock()
        replies = []
        authorization = []

        def handler(connection):
            authorization.append(connection.request.headers["Authorization"])
            connection.send('{"id":"test-1","action":"move_left"}')
            replies.append(json.loads(connection.recv(timeout=3)))

        with serve(handler, "127.0.0.1", 0) as server:
            from threading import Thread

            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.socket.getsockname()[1]
                with redirect_stdout(StringIO()) as output:
                    run_remote(camera, f"ws://127.0.0.1:{port}", "test-token")
            finally:
                server.shutdown()
                thread.join(timeout=3)

        self.assertEqual(authorization, ["Bearer test-token"])
        self.assertEqual(replies, [{"id": "test-1", "status": "accepted"}])
        camera.moveMotor.assert_called_once_with(-5, 0)
        self.assertIn("Orden del servidor WebSocket: mover a la izquierda.", output.getvalue())
        self.assertIn("Resultado: PyTapo aceptó la orden.", output.getvalue())

    def test_rejects_unsupported_or_invalid_commands(self):
        camera = Mock()
        for message in ('{"id":"1","action":"reboot"}', '{"action":"move_left"}', "invalid"):
            with self.subTest(message=message):
                self.assertEqual(command_result(camera, message)["status"], "rejected")
        camera.moveMotor.assert_not_called()

    def test_routes_all_supported_controls(self):
        camera = Mock()
        camera.getPresets.side_effect = [{}, {"7": "TFM PyTapo 1"}, {"7": "TFM PyTapo 1"}]
        camera.getDayNightMode.side_effect = ["auto", "off", "on", "auto"]
        camera.getAudioConfig.side_effect = [
            {"audio_config": {"microphone": {"mute": state, "volume": "60"}}}
            for state in ("off", "on", "off")
        ]
        actions = (
            "move_left", "move_right", "move_up", "move_down", "save_view",
            "restore_view", "get_day_night", "set_day", "set_night", "set_auto",
            "get_microphone", "mute_microphone", "unmute_microphone",
        )
        with redirect_stdout(StringIO()):
            replies = {
                action: command_result(camera, json.dumps({"id": action, "action": action}))
                for action in actions
            }
        self.assertTrue(all(reply["status"] == "accepted" for reply in replies.values()))
        self.assertEqual([call.args for call in camera.moveMotor.call_args_list],
                         [(-5, 0), (5, 0), (0, 5), (0, -5)])
        camera.savePreset.assert_called_once_with("TFM PyTapo 1")
        camera.setPreset.assert_called_once_with("7")
        self.assertEqual(replies["get_day_night"]["state"], "auto")
        self.assertEqual([call.args for call in camera.setDayNightMode.call_args_list],
                         [("off",), ("on",), ("auto",)])
        self.assertEqual(replies["get_microphone"]["state"], "off")
        self.assertEqual(replies["get_microphone"]["volume"], 60)
        self.assertEqual([call.kwargs for call in camera.setMicrophone.call_args_list],
                         [{"mute": True}, {"mute": False}])

    def test_reports_camera_error_without_exposing_details(self):
        camera = Mock()
        camera.moveMotor.side_effect = Exception("private details")
        self.assertEqual(
            command_result(camera, '{"id":"1","action":"move_left"}'),
            {"id": "1", "status": "camera_error"},
        )

    def test_rejects_insecure_remote_url(self):
        with self.assertRaises(ValueError):
            run_remote(Mock(), "ws://example.org/commands", "test-token")
