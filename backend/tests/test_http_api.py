import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient

from backend.http_api import create_app


class CameraApiTests(unittest.TestCase):
    def setUp(self):
        self.channel = Mock()
        self.client = self.enterContext(TestClient(create_app(self.channel, "credential123")))

    def request(self, method, route, *, authenticated=True):
        headers = {"Authorization": "Bearer credential123"} if authenticated else {}
        response = self.client.request(method, route, headers=headers)
        return response.status_code, response.json()

    def test_query_returns_camera_state(self):
        self.channel.send_command.return_value = {"status": "accepted", "state": "auto"}
        status, body = self.request("GET", "/api/v1/camera/day-night")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "accepted", "state": "auto"})
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
