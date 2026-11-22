"""Pruebas de configuración inicial y comprobación de vídeo."""

from contextlib import redirect_stdout
from io import StringIO
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from capture.rtsp.config import RtspConfig, RtspConfigurationError
from streaming.__main__ import initialize_camera
from streaming.camera import configure_camera, show_countdown, wait_for_camera


class CameraStartupTests(unittest.TestCase):
    @patch("streaming.camera.time.monotonic", side_effect=[0.0, 1.0, 2.0])
    def test_countdown_rewrites_one_line(self, _clock):
        stopped = Mock()
        stopped.is_set.return_value = False
        stopped.wait.return_value = False
        with redirect_stdout(StringIO()) as output:
            show_countdown("192.0.2.1", 2, stopped)
        result = output.getvalue()
        self.assertNotIn("\n", result)
        self.assertEqual(result.count("\r"), 3)
        for seconds in ("02", "01", "00"):
            self.assertIn(f"{seconds} s restantes", result)

    def test_saves_only_missing_values(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            env_file = Path(directory) / ".env"
            env_file.write_text("RTSP_HOST=192.0.2.1\nRTSP_PORT=8554\nRTSP_USERNAME=\n")
            with (
                patch("builtins.input", return_value="operador") as read,
                patch("streaming.camera.getpass", return_value="test-secret"),
                redirect_stdout(StringIO()) as output,
            ):
                config = configure_camera(interactive=True, env_file=env_file)
            self.assertEqual(config.port, 8554)
            self.assertEqual(config.username, "operador")
            self.assertEqual(env_file.read_text().count("RTSP_USERNAME="), 1)
            self.assertIn("RTSP_PASSWORD=test-secret", env_file.read_text())
            self.assertNotIn("test-secret", output.getvalue())
            read.assert_called_once_with("Usuario RTSP: ")

    @patch("streaming.camera.subprocess.run")
    def test_requires_a_video_frame(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "frame=1\n", "")
        camera = RtspConfig("192.0.2.1", "u", "p")
        with redirect_stdout(StringIO()), patch.dict(os.environ, {
            "RTSP_PASSWORD": "camera-secret",
            "FFREPORT": "file=ffmpeg.log",
            "PATH": "example-path",
        }, clear=True):
            self.assertTrue(wait_for_camera("ffmpeg", camera))
        self.assertEqual(run.call_args.kwargs["env"], {"PATH": "example-path"})

    @patch("streaming.camera.time.sleep")
    @patch("streaming.camera.time.monotonic", side_effect=[0, 0, 59, 60])
    @patch("streaming.camera.subprocess.run")
    def test_retries_only_until_deadline_when_no_frames(self, run, _clock, sleep):
        run.return_value = subprocess.CompletedProcess([], 0, "frame=0\n", "")
        camera = RtspConfig("192.0.2.1", "u", "p")
        with redirect_stdout(StringIO()) as output:
            self.assertFalse(wait_for_camera("ffmpeg", camera))
        self.assertIn("192.0.2.1", output.getvalue())
        sleep.assert_called_once_with(1)

    @patch("streaming.camera.subprocess.run")
    def test_authentication_rejection_never_prints_ffmpeg_diagnostics(self, run):
        run.return_value = subprocess.CompletedProcess([], 1, "", "401 Unauthorized")
        with redirect_stdout(StringIO()), self.assertRaisesRegex(
            RtspConfigurationError, "rechazó las credenciales"
        ):
            wait_for_camera("ffmpeg", RtspConfig("192.0.2.1", "u", "p"))

    @patch("streaming.__main__.wait_for_camera", return_value=False)
    @patch("streaming.__main__.configure_camera")
    def test_initialization_displays_failed_video_check(self, configure, _wait):
        configure.return_value = RtspConfig("192.0.2.1", "u", "p")
        with redirect_stdout(StringIO()) as output:
            self.assertIsNone(initialize_camera("ffmpeg", interactive=True))
        self.assertIn("\033[32m✓ 2.1", output.getvalue())
        self.assertIn("\033[31m✗ 2.2", output.getvalue())
        self.assertIn("\033[31m✗ 2. Verificación de la cámara", output.getvalue())
        self.assertIn("Se necesita la cámara encendida", output.getvalue())

    @patch("streaming.__main__.wait_for_camera", return_value=True)
    @patch("streaming.__main__.configure_camera")
    def test_camera_group_turns_green_after_its_checks(self, configure, _wait):
        configure.return_value = RtspConfig("192.0.2.1", "u", "p")
        with redirect_stdout(StringIO()) as output:
            self.assertEqual(initialize_camera("ffmpeg", interactive=True), configure.return_value)
        screen = output.getvalue()
        self.assertIn("\033[3A\r\033[32m✓ 2. Verificación de la cámara", screen)
        self.assertLess(screen.index("✓ 2.2"), screen.index("✓ 2. Verificación de la cámara"))
