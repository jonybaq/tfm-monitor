import json
import unittest
from threading import Thread

from websockets.exceptions import InvalidStatus
from websockets.sync.client import connect

from backend.camera_socket import CameraChannel, local_server


class CameraSocketTests(unittest.TestCase):
    def setUp(self):
        self.channel = CameraChannel("local-test")
        self.server = local_server(self.channel, port=0)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.url = f"ws://127.0.0.1:{self.server.socket.getsockname()[1]}/camera"

    def stop_server(self):
        self.server.shutdown()
        self.channel.close()
        self.thread.join(timeout=3)

    def test_rejects_connection_without_authorization(self):
        with self.assertRaises(InvalidStatus) as error:
            connect(self.url, proxy=None)
        self.assertEqual(error.exception.response.status_code, 401)
        self.assertEqual(self.channel.send_command("move_left"), {"status": "offline"})

    def test_correlates_response_with_order(self):
        with connect(
            self.url, proxy=None, additional_headers={"Authorization": "Bearer local-test"}
        ) as client:
            self.assertTrue(self.channel.wait_connected(2))
            results = []
            order = Thread(target=lambda: results.append(self.channel.send_command("get_microphone", timeout=3)))
            order.start()
            command = json.loads(client.recv(timeout=2))
            self.assertEqual(command["action"], "get_microphone")
            client.send(json.dumps({"id": "another-command", "status": "camera_error"}))
            client.send(json.dumps({
                "id": command["id"], "status": "accepted", "state": "off", "volume": 60,
            }))
            order.join(timeout=4)
            self.assertEqual(results, [{"status": "accepted", "state": "off", "volume": 60}])

    def test_returns_movement_limit_from_controller(self):
        with connect(
            self.url, proxy=None, additional_headers={"Authorization": "Bearer local-test"}
        ) as client:
            self.assertTrue(self.channel.wait_connected(2))
            results = []
            order = Thread(target=lambda: results.append(self.channel.send_command("move_left")))
            order.start()
            command = json.loads(client.recv(timeout=2))
            client.send(json.dumps({"id": command["id"], "status": "movement_limit"}))
            order.join(timeout=6)
            self.assertEqual(results, [{"status": "movement_limit"}])
