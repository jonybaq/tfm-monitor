"""Regression tests for the experimental sender without requiring PyAV."""

from fractions import Fraction
from types import SimpleNamespace
import unittest

from streaming.pyav_sender import format_progress, set_audio_timestamp, set_video_timestamp


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
