import sys
import unittest
from pathlib import Path

import numpy as np


SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import vad.coordinator as coordinator_module
from vad.coordinator import (
    ChunkedVadCoordinator,
    ParallelVadConfig,
    _align_strength_patch_range,
    _covered_ratio,
)
from vad.models import SpeechSegment, VadAnalysisRequest, VadTimeRange
from vad.store import InMemoryVadResultStore


class TestChunkedVadCoordinator(unittest.TestCase):
    def test_should_use_parallel_requires_long_full_pipeline(self):
        request = VadAnalysisRequest(
            media_path="demo.wav",
            time_range=VadTimeRange(0.0, 1800.0),
            media_duration_sec=1800.0,
            include_amplitude=True,
            include_vad=True,
        )
        config = ParallelVadConfig(
            parallel_workers=4,
            slice_minutes=2,
            parallel_min_duration_seconds=900,
        )

        self.assertTrue(ChunkedVadCoordinator.should_use_parallel(request, config))

        vad_only_request = VadAnalysisRequest(
            media_path="demo.wav",
            time_range=VadTimeRange(0.0, 1800.0),
            media_duration_sec=1800.0,
            include_amplitude=False,
            include_vad=True,
        )
        self.assertFalse(ChunkedVadCoordinator.should_use_parallel(vad_only_request, config))

        short_request = VadAnalysisRequest(
            media_path="demo.wav",
            time_range=VadTimeRange(0.0, 600.0),
            media_duration_sec=600.0,
            include_amplitude=True,
            include_vad=True,
        )
        self.assertFalse(ChunkedVadCoordinator.should_use_parallel(short_request, config))

    def test_align_strength_patch_range_snaps_to_strength_bins(self):
        aligned = _align_strength_patch_range(
            time_range=VadTimeRange(1.01, 3.99),
            media_duration_sec=10.0,
            points_per_second=4,
        )

        self.assertIsNotNone(aligned)
        self.assertEqual(aligned.start_index, 4)
        self.assertEqual(aligned.time_range.start_sec, 1.0)
        self.assertEqual(aligned.time_range.end_sec, 4.0)

    def test_covered_ratio_uses_total_range(self):
        ratio = _covered_ratio(
            processed_ranges=[
                VadTimeRange(0.0, 2.0),
                VadTimeRange(2.0, 4.0),
                VadTimeRange(8.0, 12.0),
            ],
            total_range=VadTimeRange(0.0, 10.0),
        )

        self.assertAlmostEqual(ratio, 0.6)

    def test_resolve_slice_result_drops_last_chunk_and_rewinds(self):
        coordinator = ChunkedVadCoordinator(lambda: None)
        confirmed_range, confirmed_segments, next_cursor = coordinator._resolve_slice_result(
            analysis_range=VadTimeRange(120.0, 240.0),
            worker_range=VadTimeRange(100.0, 400.0),
            speech_segments=[
                SpeechSegment(130.0, 160.0),
                SpeechSegment(200.0, 230.0),
            ],
        )

        self.assertEqual((confirmed_range.start_sec, confirmed_range.end_sec), (120.0, 200.0))
        self.assertEqual(
            [(segment.start_sec, segment.end_sec) for segment in confirmed_segments],
            [(130.0, 160.0)],
        )
        self.assertEqual(next_cursor, 200.0)

    def test_resolve_slice_result_keeps_full_slice_for_long_opening_speech(self):
        coordinator = ChunkedVadCoordinator(lambda: None)
        confirmed_range, confirmed_segments, next_cursor = coordinator._resolve_slice_result(
            analysis_range=VadTimeRange(120.0, 240.0),
            worker_range=VadTimeRange(100.0, 400.0),
            speech_segments=[SpeechSegment(120.0, 230.0)],
        )

        self.assertEqual((confirmed_range.start_sec, confirmed_range.end_sec), (120.0, 240.0))
        self.assertEqual(
            [(segment.start_sec, segment.end_sec) for segment in confirmed_segments],
            [(120.0, 230.0)],
        )
        self.assertEqual(next_cursor, 240.0)

    def test_run_emits_partial_updates_and_commits_final_result(self):
        class FakeEngine:
            def analyze_range(self, media_path, time_range, media_duration_sec, should_stop=None):
                if should_stop is not None and should_stop():
                    return []
                duration = time_range.duration_sec
                if duration <= 40.0:
                    return [SpeechSegment(time_range.start_sec + 5.0, time_range.end_sec - 5.0)]
                return [
                    SpeechSegment(time_range.start_sec + 10.0, time_range.start_sec + 20.0),
                    SpeechSegment(time_range.end_sec - 20.0, time_range.end_sec - 10.0),
                ]

        def fake_strength_extractor(
            media_path,
            time_range,
            points_per_second=50,
            sample_rate=8000,
            should_stop=None,
            normalize=False,
        ):
            sample_count = max(int(round(time_range.duration_sec * points_per_second)), 1)
            return np.full(sample_count, 0.25, dtype=np.float32)

        final_store = InMemoryVadResultStore()
        coordinator = ChunkedVadCoordinator(lambda: FakeEngine(), final_store=final_store)
        request = VadAnalysisRequest(
            media_path="demo.wav",
            time_range=VadTimeRange(0.0, 1000.0),
            media_duration_sec=1000.0,
            include_amplitude=True,
            include_vad=True,
            amplitude_points_per_second=2,
            amplitude_sample_rate=8,
        )
        config = ParallelVadConfig(
            parallel_workers=2,
            slice_minutes=2,
            parallel_min_duration_seconds=900,
        )
        partial_updates = []
        original_strength_extractor = coordinator_module.extract_audio_strength_range_series
        coordinator_module.extract_audio_strength_range_series = fake_strength_extractor
        try:
            output = coordinator.run(
                request=request,
                config=config,
                on_partial_update=partial_updates.append,
            )
        finally:
            coordinator_module.extract_audio_strength_range_series = original_strength_extractor

        self.assertGreater(len(partial_updates), 0)
        self.assertIsNotNone(output.vad_result)
        self.assertIsNotNone(output.amplitude_series)
        self.assertEqual(len(output.amplitude_series), 2000)
        self.assertAlmostEqual(output.amplitude_peak, 0.25)
        self.assertTrue(np.any(output.amplitude_series > 0))

        cached = final_store.get_result("demo.wav", "silero")
        self.assertIsNotNone(cached)
        self.assertGreaterEqual(len(cached.speech_segments), 10)
        self.assertEqual(
            (cached.speech_segments[0].start_sec, cached.speech_segments[0].end_sec),
            (10.0, 20.0),
        )
        self.assertEqual(
            (cached.speech_segments[-1].start_sec, cached.speech_segments[-1].end_sec),
            (980.0, 990.0),
        )


if __name__ == "__main__":
    unittest.main()
