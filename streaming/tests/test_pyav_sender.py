"""Regression tests for the experimental sender without requiring PyAV."""

from contextlib import nullcontext, redirect_stdout
from fractions import Fraction
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from capture.rtsp.config import RtspConfig, RtspConfigurationError
from streaming.config import StreamDestination, StreamingError
from streaming.pyav_sender import (
    PyAvSender, format_progress, set_audio_timestamp, set_video_timestamp,
)


class FakeMediaError(Exception):
    errno = 22


class FakeUnauthorized(FakeMediaError):
    pass


class SenderTests(unittest.TestCase):
    def setUp(self):
        self.av = Mock()
        self.av.error = SimpleNamespace(
            FFmpegError=FakeMediaError, HTTPUnauthorizedError=FakeUnauthorized,
        )
        with patch.dict("sys.modules", {"av": self.av}):
            self.sender = PyAvSender()
        self.camera = RtspConfig("localhost", "test-user", "test-value")
        self.destination = StreamDestination("local", "localhost", transport="rtsp")
        self.connected = Mock()

    def send(self, *, interactive=False):
        return self.sender.send(
            self.camera, self.destination, start_timeout=3,
            on_connected=self.connected, interactive=interactive,
        )

    def test_missing_library_reports_installation_error(self):
        with patch.dict("sys.modules", {"av": None}):
            with self.assertRaisesRegex(StreamingError, "PyAV no está disponible"):
                PyAvSender()

    def test_probe_recovers_after_read_error_and_waits_for_first_frame(self):
        source = Mock()
        source.streams.video = [object()]
        source.decode.side_effect = [iter(()), iter((object(),))]
        self.av.open.side_effect = [
            FakeMediaError(), nullcontext(source), nullcontext(source),
        ]
        with patch("streaming.pyav_sender.time.sleep") as sleep:
            self.assertTrue(self.sender.probe(self.camera, interactive=False, label=""))
        self.assertEqual(sleep.call_count, 2)
        source.decode.assert_called_with(video=0)

    def test_interactive_probe_cleans_up_countdown_after_authentication_error(self):
        self.av.open.side_effect = FakeUnauthorized("internal detail")
        with patch("streaming.pyav_sender.threading.Thread") as thread:
            with self.assertRaisesRegex(RtspConfigurationError, "La cámara rechazó"):
                self.sender.probe(self.camera, interactive=True, label="prueba")
        thread.return_value.start.assert_called_once()
        thread.return_value.join.assert_called_once()
        self.assertTrue(thread.call_args.kwargs["args"][2].is_set())

    def test_probe_expires_without_opening_camera_after_deadline(self):
        with patch("streaming.pyav_sender.time.monotonic", side_effect=[0, 60]):
            self.assertFalse(self.sender.probe(self.camera, interactive=False, label=""))
        self.av.open.assert_not_called()

    def test_send_distinguishes_camera_and_receiver_connection_errors(self):
        source = Mock()
        source.streams = SimpleNamespace(video=[object()], audio=[object()])
        for side_effect, expected in (
            ([FakeMediaError("private detail")], "Esperando conexión de la cámara"),
            ([nullcontext(source), FakeMediaError("private detail")], "Esperando receptor local"),
        ):
            self.av.open.side_effect = side_effect
            with self.assertLogs("streaming.pyav_sender", level="WARNING") as logs:
                self.assertEqual(self.send(), expected)
            self.assertIn("código 22", logs.output[0])
            self.assertNotIn("private detail", logs.output[0])
        self.connected.assert_not_called()

    def test_receiver_auth_failure_reports_controlled_message(self):
        source = Mock()
        source.streams = SimpleNamespace(video=[object()], audio=[object()])
        self.av.open.side_effect = [nullcontext(source), FakeUnauthorized()]
        with self.assertRaisesRegex(StreamingError, "El receptor rechazó"):
            self.send()

    def test_send_requires_rtsp_and_the_configured_tracks(self):
        self.destination = StreamDestination("local", "localhost")
        with self.assertRaisesRegex(StreamingError, "requiere RTSP"):
            self.send()
        self.av.open.assert_not_called()
        self.destination = StreamDestination("local", "localhost", transport="rtsp")
        source = Mock()
        source.streams = SimpleNamespace(video=[object()], audio=[])
        self.av.open.return_value = nullcontext(source)
        with self.assertRaisesRegex(StreamingError, "pistas requeridas"):
            self.send()
        self.connected.assert_not_called()

    def test_sender_muxes_video_and_opus_and_announces_only_once(self):
        self.destination = StreamDestination(
            "local", "localhost", transport="rtsp", low_latency=True,
        )
        video, audio = object(), object()
        source, output = Mock(), Mock()
        source.streams = SimpleNamespace(video=[video], audio=[audio])
        empty = SimpleNamespace(stream=video, size=0)
        first = SimpleNamespace(stream=video, size=100)
        second = SimpleNamespace(stream=video, size=110)
        audio_packet, decoded, sample, encoded = Mock(), Mock(), Mock(), Mock()
        audio_packet.stream = audio
        audio_packet.decode.return_value = [decoded]
        sample.samples = 960
        encoded.size = 80
        source.demux.return_value = iter([empty, first, audio_packet, second])
        output.add_stream.return_value.encode.return_value = [encoded]
        self.av.audio.resampler.AudioResampler.return_value.resample.return_value = [sample]
        self.av.open.side_effect = [nullcontext(source), nullcontext(output)]

        with patch("streaming.pyav_sender.time.monotonic", side_effect=[0, 0, 0, 0, 1, 2]):
            with redirect_stdout(StringIO()) as console:
                self.assertEqual(self.send(interactive=True), "Envío interrumpido. Volviendo a conectar")

        self.assertEqual(self.av.open.call_args_list[0].kwargs["options"]["fflags"], "+nobuffer")
        self.assertEqual(output.mux.call_count, 3)
        self.assertEqual(output.mux.call_args_list[0].args, (first,))
        self.assertEqual(output.mux.call_args_list[1].args, (encoded,))
        self.assertEqual(output.mux.call_args_list[2].args, (second,))
        self.assertEqual((first.pts, second.pts, sample.pts), (0, 1, 0))
        self.connected.assert_called_once()
        self.assertIn("frame=2", console.getvalue())


class VideoTimestampTests(unittest.TestCase):
    def test_replaces_duplicate_camera_timestamps_with_increasing_values(self):
        packets = [
            SimpleNamespace(pts=126559, dts=126559, time_base=Fraction(1, 90000))
            for _ in range(3)
        ]
        for frame_index, packet in enumerate(packets):
            set_video_timestamp(packet, frame_index)

        self.assertEqual(
            [(packet.pts, packet.dts, packet.time_base) for packet in packets],
            [(index, index, Fraction(1, 30)) for index in range(3)],
        )

    def test_audio_clock_advances_by_the_number_of_resampled_samples(self):
        first = SimpleNamespace(pts=90000, samples=960)
        second = SimpleNamespace(pts=90000, samples=480)
        next_index = set_audio_timestamp(first, 0)
        self.assertEqual(set_audio_timestamp(second, next_index), 1440)
        self.assertEqual((first.pts, second.pts), (0, 960))
        self.assertEqual(second.time_base, Fraction(1, 48000))


class ProgressTests(unittest.TestCase):
    def test_progress_reports_interval_fps_and_total_media_bitrate(self):
        self.assertEqual(
            format_progress(60, 24, 1.2, 500_000),
            "frame=60  fps=20.0  out_time=2.0s  bitrate=2000kbits/s",
        )
