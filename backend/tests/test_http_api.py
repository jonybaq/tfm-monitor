import unittest
from http.client import HTTPConnection
from threading import Thread
from unittest.mock import Mock

from backend.http_api import create_http_server


class CameraApiTests(unittest.TestCase):
    def setUp(self):
        self.channel = Mock()
        self.server = create_http_server(self.channel, "credential123", port=0)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def request(self, method, route, *, authenticated=True):
        connection = HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        self.addCleanup(connection.close)
        headers = {"Authorization": "Bearer credential123"} if authenticated else {}
        connection.request(method, route, headers=headers)
        response = connection.getresponse()
        return response.status, response.read()

    def test_query_returns_camera_state(self):
        self.channel.send_command.return_value = {"status": "accepted", "state": "auto"}
        status, body = self.request("GET", "/api/v1/camera/day-night")
        self.assertEqual(status, 200)
        self.assertIn(b'"state": "auto"', body)
        self.channel.send_command.assert_called_once_with("get_day_night")

    def test_action_preserves_movement_limit(self):
        self.channel.send_command.return_value = {"status": "movement_limit"}
        self.assertEqual(self.request("POST", "/api/v1/camera/actions/move_left")[0], 409)
        self.channel.send_command.assert_called_once_with("move_left")

    def test_unavailable_camera_returns_503(self):
        self.channel.send_command.return_value = {"status": "offline"}
        self.assertEqual(self.request("GET", "/api/v1/camera/microphone")[0], 503)

    def test_unauthenticated_and_unknown_actions_do_not_reach_camera(self):
        self.assertEqual(
            self.request("POST", "/api/v1/camera/actions/move_left", authenticated=False)[0], 401,
        )
        self.assertEqual(self.request("POST", "/api/v1/camera/actions/reboot")[0], 404)
        self.channel.send_command.assert_not_called()
