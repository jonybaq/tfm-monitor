"""Pruebas de configuración RTSP sin secretos ni red."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rtsp.config import RtspConfig, RtspConfigurationError


class RtspConfigTests(unittest.TestCase):
    def test_rejects_invalid_addresses_from_environment(self) -> None:
        for host in ("192.0.2.1/stream1", "camera.local:554", "999.1.1.1", "cam..local"):
            with self.subTest(host=host), patch.dict(os.environ, {
                "RTSP_HOST": host, "RTSP_USERNAME": "user", "RTSP_PASSWORD": "secret",
            }, clear=True):
                with self.assertRaisesRegex(RtspConfigurationError, "RTSP_HOST"):
                    RtspConfig.from_environment(Path("nonexistent-test.env"))

    def test_rejects_invalid_stream_paths_from_local_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            for path in ("", "/", "stream 1", "stream1?x=1", "stream1#fragment", "stream%zz"):
                with self.subTest(path=path), patch.dict(os.environ, {}, clear=True):
                    env_file.write_text(
                        "RTSP_HOST=camera.local\nRTSP_USERNAME=user\nRTSP_PASSWORD=secret\n"
                        f"RTSP_STREAM_PATH={path}\n",
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(RtspConfigurationError, "RTSP_STREAM_PATH"):
                        RtspConfig.from_environment(env_file)

    def test_accepts_ipv6_and_preserves_nested_path(self) -> None:
        with patch.dict(os.environ, {
            "RTSP_HOST": "2001:db8::1",
            "RTSP_USERNAME": "user",
            "RTSP_PASSWORD": "secret",
            "RTSP_STREAM_PATH": "/live/stream%32",
        }, clear=True):
            config = RtspConfig.from_environment(Path("nonexistent-test.env"))
        self.assertEqual(config.url, "rtsp://user:secret@[2001:db8::1]:554/live/stream%32")

    def test_repr_and_str_hide_credentials(self) -> None:
        config = RtspConfig("127.0.0.1", "usuario_ficticio", "clave_ficticia")
        for output in (repr(config), str(config)):
            self.assertNotIn(config.username, output)
            self.assertNotIn(config.password, output)
            self.assertIn(config.host, output)

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
