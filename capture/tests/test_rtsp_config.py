"""Pruebas de configuración RTSP sin secretos ni red."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rtsp.config import RtspConfig, RtspConfigurationError


class RtspConfigTests(unittest.TestCase):
    def test_builds_url_and_escapes_credentials(self) -> None:
        config = RtspConfig("192.168.1.10", "user@example", "p@ss word")

        self.assertEqual(
            config.url,
            "rtsp://user%40example:p%40ss%20word@192.168.1.10:554/stream1",
        )

    def test_rejects_missing_required_environment_values(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RtspConfigurationError):
                RtspConfig.from_environment(Path("nonexistent-test.env"))

    def test_reads_rtsp_values_from_local_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            env_file = Path(temporary_directory) / ".env"
            env_file.write_text(
                "RTSP_HOST=192.168.1.10\n"
                "RTSP_USERNAME=camera_user\n"
                "RTSP_PASSWORD=camera_password\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                config = RtspConfig.from_environment(env_file)

        self.assertEqual(config.host, "192.168.1.10")
        self.assertEqual(config.username, "camera_user")
