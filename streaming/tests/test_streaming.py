"""Pruebas del lanzador sin cámara ni credenciales reales."""

import os
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from capture.rtsp.config import RtspConfig
from streaming.__main__ import (
    Attempt, CAMERA_WAIT, ffmpeg_command, find_ffmpeg, initialize_ffmpeg,
    main, prepare_ffmpeg, publish,
    publish_once,
)
from streaming.config import StreamDestination, choose_mode


class StreamingConfigTests(unittest.TestCase):
    def test_interactive_local_uses_loopback(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True), patch(
            "streaming.config.choose_mode", return_value="local"
        ), patch("streaming.config.choose_transport", return_value="srt"), patch(
            "builtins.input", side_effect=["", ""]
        ), redirect_stdout(StringIO()):
            env_file = Path(directory) / ".env"
            env_file.write_text("STREAMING_AZURE_HOST=azure.example.com\n")
            config = StreamDestination.from_environment(interactive=True, env_file=env_file)
            self.assertIn("STREAMING_LOCAL_HOST=127.0.0.1", env_file.read_text())
            self.assertIn("STREAMING_LOCAL_PORT=8890", env_file.read_text())
            self.assertIn("STREAMING_AZURE_HOST=azure.example.com", env_file.read_text())
        self.assertEqual((config.mode, config.host), ("local", "127.0.0.1"))

    def test_interactive_azure_asks_for_host_and_secret(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True), patch(
            "streaming.config.choose_mode", return_value="azure"
        ), patch("streaming.config.choose_transport", return_value="srt"), patch(
            "builtins.input", side_effect=["media.example.com", "9990"]
        ), patch("streaming.config.getpass", return_value="test-passphrase"), redirect_stdout(StringIO()):
            env_file = Path(directory) / ".env"
            config = StreamDestination.from_environment(interactive=True, env_file=env_file)
            with patch("builtins.input") as prompt:
                self.assertEqual(
                    StreamDestination.from_environment(interactive=True, env_file=env_file),
                    config,
                )
            prompt.assert_not_called()
        self.assertEqual((config.mode, config.host), ("azure", "media.example.com"))
        self.assertEqual(config.passphrase, "test-passphrase")
        self.assertEqual(config.port, 9990)

    def test_configured_mode_bypasses_menu(self):
        with TemporaryDirectory() as directory, patch.dict(
            os.environ, {"STREAMING_MODE": "local", "STREAMING_TRANSPORT": "srt"}, clear=True
        ), patch(
            "streaming.config.choose_mode"
        ) as prompt:
            env_file = Path(directory) / ".env"
            env_file.write_text("STREAMING_LOCAL_HOST=localhost\nSTREAMING_LOCAL_PORT=8890\n")
            StreamDestination.from_environment(interactive=True, env_file=env_file)
        prompt.assert_not_called()

    @unittest.skipUnless(sys.platform == "win32", "Menú de consola de Windows")
    def test_arrow_keys_move_selection_and_enter_confirms(self):
        for keys, expected in (
            (["\r"], "local"),
            (["\xe0", "P", "\r"], "azure"),
            (["\xe0", "P", "\xe0", "H", "\r"], "local"),
        ):
            with self.subTest(keys=keys), patch(
                "msvcrt.getwch", side_effect=keys
            ), redirect_stdout(StringIO()) as output:
                self.assertEqual(choose_mode(), expected)
                self.assertIn("> Local\n  Azure\n", output.getvalue())
                self.assertTrue(output.getvalue().endswith(
                    "\033[4A\r" + "\033[2K\033[1B" * 3 + "\033[2K\033[3A"
                ))
                self.assertNotIn("\033[J", output.getvalue())

    def test_local_is_default(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            config = StreamDestination.from_environment(env_file=Path(directory) / ".env")

        self.assertEqual(config.mode, "local")
        self.assertEqual(urlsplit(config.url).netloc, "127.0.0.1:8890")
        self.assertNotIn("passphrase", config.url)

    def test_azure_requires_host_and_passphrase(self):
        with TemporaryDirectory() as directory, patch.dict(
            os.environ, {"STREAMING_MODE": "azure"}, clear=True
        ):
            env_file = Path(directory) / ".env"
            with self.assertRaisesRegex(ValueError, "STREAMING_AZURE_HOST"):
                StreamDestination.from_environment(env_file=env_file)
            os.environ["STREAMING_HOST"] = "media.example.com"
            with self.assertRaisesRegex(ValueError, "frase SRT"):
                StreamDestination.from_environment(env_file=env_file)

    def test_azure_command_keeps_video_and_encodes_audio(self):
        destination = StreamDestination("azure", "media.example.com", "example & phrase")
        camera = RtspConfig("127.0.0.1", "camera", "test-password")
        command = ffmpeg_command("ffmpeg", camera, destination)
        query = parse_qs(urlsplit(command[-1]).query)

        self.assertEqual(query["passphrase"], ["example & phrase"])
        self.assertEqual(query["streamid"], ["publish:tapo"])
        self.assertNotIn(destination.passphrase, repr(destination))
        self.assertIn("copy", command)
        self.assertIn("libopus", command)
        self.assertEqual(command[command.index("-i") + 1], camera.url)

    def test_audio_can_be_disabled(self):
        with patch.dict(os.environ, {"STREAMING_AUDIO": "off"}, clear=True):
            config = StreamDestination.from_environment()
        command = ffmpeg_command("ffmpeg", RtspConfig("localhost", "u", "p"), config)

        self.assertIn("-an", command)
        self.assertNotIn("0:a:0", command)

    def test_local_rtsp_uses_separate_port_and_tcp(self):
        with TemporaryDirectory() as directory, patch.dict(
            os.environ, {"STREAMING_MODE": "local", "STREAMING_TRANSPORT": "rtsp"},
            clear=True,
        ):
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "STREAMING_LOCAL_HOST=localhost\nSTREAMING_LOCAL_PORT=8890\n"
                "STREAMING_LOCAL_RTSP_PORT=18554\n"
            )
            destination = StreamDestination.from_environment(env_file=env_file)
        command = ffmpeg_command("ffmpeg", RtspConfig("localhost", "u", "p"), destination)
        self.assertEqual(
            command[-5:], ["-f", "rtsp", "-rtsp_transport", "tcp", "rtsp://localhost:18554/tapo"]
        )
        self.assertIn("libopus", command)

    def test_azure_rtsp_uses_public_host_and_publisher_credentials(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {
            "STREAMING_MODE": "azure",
            "STREAMING_TRANSPORT": "rtsp",
            "STREAMING_AZURE_HOST": "public.example.com",
            "STREAMING_AZURE_PUBLISH_PASSWORD": "example-password-123",
        }, clear=True):
            env_file = Path(directory) / ".env"
            destination = StreamDestination.from_environment(env_file=env_file)
            self.assertEqual(
                destination.url,
                "rtsp://tfm-publisher:example-password-123@public.example.com:8554/tapo",
            )
            self.assertNotIn("example-password-123", repr(destination))
            del os.environ["STREAMING_AZURE_PUBLISH_PASSWORD"]
            with self.assertRaisesRegex(ValueError, "STREAMING_AZURE_PUBLISH_PASSWORD"):
                StreamDestination.from_environment(env_file=env_file)

    def test_azure_srt_adds_publisher_credentials_when_configured(self):
        destination = StreamDestination(
            "azure", "public.example.com", "example-srt",
            publish_password="example-password-123",
        )
        query = parse_qs(urlsplit(destination.url).query)
        self.assertEqual(query["streamid"], ["publish:tapo:tfm-publisher:example-password-123"])
        self.assertEqual(query["passphrase"], ["example-srt"])

    def test_low_latency_option_is_applied_only_to_local_rtsp_input(self):
        camera = RtspConfig("localhost", "u", "p")
        for mode, transport, enabled, expected in (
            ("local", "rtsp", True, True),
            ("local", "rtsp", False, False),
            ("local", "srt", True, False),
            ("azure", "srt", True, False),
        ):
            with self.subTest(mode=mode, transport=transport, enabled=enabled):
                destination = StreamDestination(
                    mode, "localhost", transport=transport, low_latency=enabled
                )
                command = ffmpeg_command("ffmpeg", camera, destination)
                self.assertEqual("+nobuffer" in command, expected)
                if expected:
                    self.assertLess(command.index("+nobuffer"), command.index("-i"))

    def test_low_latency_keeps_video_timestamp_filter_and_audio(self):
        camera = RtspConfig("localhost", "u", "p")
        destination = StreamDestination(
            "local", "localhost", transport="rtsp", low_latency=True
        )
        command = ffmpeg_command("ffmpeg", camera, destination)
        self.assertIn("setts=pts=N/(30*TB):dts=N/(30*TB)", command)
        self.assertIn("libopus", command)


class StreamingProcessTests(unittest.TestCase):
    @patch("streaming.__main__.time.monotonic", side_effect=[0, 0, 60, 60])
    @patch("streaming.__main__.time.sleep")
    @patch("streaming.__main__.publish_once", return_value="Esperando receptor local")
    def test_receiver_check_expires_after_sixty_seconds(self, attempt, sleep, _clock):
        destination = StreamDestination("local", "127.0.0.1")
        with redirect_stdout(StringIO()) as output, self.assertLogs() as logs:
            self.assertEqual(publish(["ffmpeg"], destination, interactive=False), 1)
        attempt.assert_called_once()
        sleep.assert_called_once_with(0)
        self.assertIn("127.0.0.1:8890", output.getvalue())
        self.assertIn("✓ 3. Destino elegido · Local", output.getvalue())
        self.assertIn("✓ 4. Tipo de transmisión elegido · SRT", output.getvalue())
        self.assertIn("✗ 5.", output.getvalue())
        self.assertIn("Esperando receptor local", logs.output[0])

    @patch("streaming.__main__.publish_once")
    def test_receiver_check_confirms_when_publication_starts(self, attempt):
        def start_publishing(_command, _destination, *, on_connected, start_timeout, interactive):
            on_connected()
            raise KeyboardInterrupt

        attempt.side_effect = start_publishing
        destination = StreamDestination("azure", "media.example.com")
        with redirect_stdout(StringIO()) as output, self.assertRaises(KeyboardInterrupt):
            publish(["ffmpeg"], destination, interactive=False)
        self.assertIn("✓ 3. Destino elegido · Azure", output.getvalue())
        self.assertIn("✓ 5.", output.getvalue())
        self.assertNotIn("✗ 5.", output.getvalue())

    @patch("streaming.__main__.prepare_ffmpeg")
    def test_initialization_reports_green_success_or_red_failure(self, prepare):
        for executable, status in (
            ("ffmpeg.exe", "\033[32m✓"),
            (None, "\033[31m✗"),
        ):
            with self.subTest(executable=executable), redirect_stdout(StringIO()) as output:
                prepare.return_value = executable
                self.assertEqual(initialize_ffmpeg(interactive=True), executable)
                self.assertIn("Proceso de inicialización", output.getvalue())
                self.assertIn(status, output.getvalue())
                self.assertIn(
                    ".\033[K\r" + status,
                    output.getvalue(),
                )
                self.assertEqual(
                    "Se necesita FFmpeg para establecer la conexión." in output.getvalue(),
                    executable is None,
                )

    @patch("streaming.__main__.initialize_ffmpeg", return_value=None)
    @patch("streaming.__main__.initialize_camera")
    def test_missing_ffmpeg_exits_before_opening_camera(self, camera, _initialize):
        self.assertEqual(main(), 1)
        camera.assert_not_called()

    @patch("streaming.__main__.shutil.which", return_value=None)
    def test_finds_winget_installation_without_path(self, _which):
        with TemporaryDirectory() as directory, patch.dict(
            os.environ, {"LOCALAPPDATA": directory}
        ):
            binary = (
                Path(directory) / "Microsoft" / "WinGet" / "Packages"
                / "Gyan.FFmpeg_example" / "ffmpeg-9.0" / "bin" / "ffmpeg.exe"
            )
            binary.parent.mkdir(parents=True)
            binary.touch()
            self.assertEqual(find_ffmpeg(), str(binary))

    @patch("streaming.__main__.find_ffmpeg", return_value=None)
    @patch("streaming.__main__.shutil.which", return_value="winget")
    @patch("streaming.__main__.subprocess.run")
    def test_declining_does_not_install(self, run, _which, _find):
        with patch("streaming.__main__.choose_option", return_value=0):
            self.assertIsNone(prepare_ffmpeg(interactive=True))
        run.assert_not_called()

    @patch("streaming.__main__.find_ffmpeg", side_effect=[None, "ffmpeg.exe"])
    @patch("streaming.__main__.shutil.which", return_value="winget")
    @patch("streaming.__main__.subprocess.run")
    def test_confirming_installs_and_finds_binary(self, run, _which, _find):
        run.return_value.returncode = 0
        with patch("streaming.__main__.choose_option", return_value=1):
            self.assertEqual(prepare_ffmpeg(interactive=True), "ffmpeg.exe")
        run.assert_called_once_with(
            ["winget", "install", "--id", "Gyan.FFmpeg", "--exact"], check=False
        )

    def run_fake_process(self, *lines, mode="local"):
        code = "import sys; print(" + repr("\n".join(lines)) + ", file=sys.stderr)"
        return publish_once(
            [sys.executable, "-c", code], StreamDestination(mode, "localhost")
        )

    def test_camera_unavailable(self):
        self.assertEqual(self.run_fake_process("Connection refused"), CAMERA_WAIT)

    def test_waits_for_the_configured_receiver(self):
        for mode, message in (
            ("local", "Esperando receptor local"),
            ("azure", "Esperando receptor en la nube"),
        ):
            with self.subTest(mode=mode):
                self.assertEqual(
                    self.run_fake_process("Input #0, rtsp, from", mode=mode), message
                )

    def test_interrupted_output_is_retried(self):
        self.assertEqual(
            self.run_fake_process("Input #0, rtsp,", "Output #0, mpegts,", "frame=3"),
            "Envío interrumpido. Volviendo a conectar",
        )

    def test_missing_track_is_a_configuration_error(self):
        with self.assertRaisesRegex(ValueError, "pistas requeridas"):
            self.run_fake_process("Stream map '0:a:0' matches no streams")

    def test_repeated_frame_does_not_reset_watchdog(self):
        attempt = Attempt()
        attempt.read("frame=5", 10.0)
        attempt.read("frame=5", 15.0)
        self.assertEqual(attempt.last_progress, 10.0)

    def test_summarizes_only_selected_ffmpeg_progress_fields(self):
        attempt = Attempt()
        for line in (
            "frame=42", "fps=30.0", "out_time=00:00:01.40", "bitrate=2000kbits/s",
            "speed=1.0x", "unexpected=private-url", "progress=continue",
        ):
            attempt.read(line + "\n", 10.0)
        self.assertEqual(
            attempt.stats,
            "frame=42  fps=30.0  out_time=00:00:01.40  bitrate=2000kbits/s  speed=1.0x",
        )

    @patch("streaming.__main__.time.sleep")
    @patch("streaming.__main__.publish_once")
    @patch("streaming.__main__.initialize_camera")
    @patch("streaming.__main__.shutil.which", return_value="ffmpeg")
    def test_supervisor_retries_and_stops(self, _which, camera, publish, sleep):
        camera.return_value = RtspConfig("localhost", "u", "p")
        publish.side_effect = [
            CAMERA_WAIT, "Esperando receptor local",
            "Envío interrumpido. Volviendo a conectar", KeyboardInterrupt(),
        ]
        settings = {
            "STREAMING_MODE": "local",
            "STREAMING_HOST": "127.0.0.1",
            "STREAMING_PORT": "8890",
            "STREAMING_TRANSPORT": "srt",
        }
        with patch.dict(os.environ, settings, clear=True), self.assertLogs(), redirect_stdout(StringIO()):
            self.assertEqual(main(), 0)
        self.assertEqual(publish.call_count, 4)
        self.assertEqual(sleep.call_count, 3)
