import sys
import unittest
from pathlib import Path

import numpy as np


SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import vad.service as service_module
from vad.auto_slicer import choose_auto_cut_point, get_slice_length_preset
from vad.models import AudioStrengthPatch, SpeechSegment, VadAnalysisRequest, VadTimeRange
from vad.service import VadApplicationService


class FakeEngine:
    engine_key = "fake"

    def analyze_range(self, media_path, time_range, media_duration_sec, should_stop=None):
        return []


class TestAutoSlicer(unittest.TestCase):
    def test_long_silence_biases_cut_toward_right_edge(self):
        cut = choose_auto_cut_point(
            base_sec=0.0,
            duration_sec=1200.0,
            preset=get_slice_length_preset("~10min"),
            speech_segments=[
                SpeechSegment(540.0, 550.0),
                SpeechSegment(650.0, 660.0),
            ],
        )

        self.assertEqual(cut, 647.0)

    def test_hard_limit_does_not_cut_after_target(self):
        cut = choose_auto_cut_point(
            base_sec=0.0,
            duration_sec=120.0,
            preset=get_slice_length_preset("<1min"),
            speech_segments=[SpeechSegment(30.0, 40.0)],
        )

        self.assertLessEqual(cut, 60.0)

    def test_strength_fallback_uses_lowest_point_when_no_silence_gap(self):
        patch = AudioStrengthPatch(
            time_range=VadTimeRange(30.0, 60.0),
            start_index=30,
            values=np.asarray([1.0, 0.2, 0.0, 0.4, 0.9], dtype=np.float32),
        )

        cut = choose_auto_cut_point(
            base_sec=0.0,
            duration_sec=120.0,
            preset=get_slice_length_preset("<1min"),
            speech_segments=[SpeechSegment(30.0, 60.0)],
            strength_patch=patch,
        )

        self.assertAlmostEqual(cut, 42.0)


class TestRangeStrengthService(unittest.TestCase):
    def test_range_amplitude_request_returns_patch_not_full_series(self):
        def fake_range_extractor(
            media_path,
            time_range,
            points_per_second=50,
            sample_rate=8000,
            should_stop=None,
            normalize=False,
        ):
            return np.full(int(time_range.duration_sec * points_per_second), 0.25, dtype=np.float32)

        original_extractor = service_module.extract_audio_strength_range_series
        service_module.extract_audio_strength_range_series = fake_range_extractor
        try:
            service = VadApplicationService([FakeEngine()])
            output = service.request_analysis(
                VadAnalysisRequest(
                    media_path="demo.wav",
                    time_range=VadTimeRange(10.0, 20.0),
                    media_duration_sec=100.0,
                    engine_key="fake",
                    include_amplitude=True,
                    include_vad=False,
                    amplitude_points_per_second=2,
                    amplitude_sample_rate=8,
                )
            )
        finally:
            service_module.extract_audio_strength_range_series = original_extractor

        self.assertIsNone(output.amplitude_series)
        self.assertIsNotNone(output.amplitude_patch)
        self.assertEqual(output.amplitude_patch.start_index, 20)
        self.assertEqual(len(output.amplitude_patch.values), 20)
        self.assertAlmostEqual(output.amplitude_peak, 0.25)


if __name__ == "__main__":
    unittest.main()
