import sys
import unittest
from pathlib import Path


SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from vad.models import SpeechSegment, VadTimeRange
from vad.store import InMemoryVadResultStore


class TestInMemoryVadResultStore(unittest.TestCase):
    def test_merge_range_replaces_overlap_and_keeps_outside_segments(self):
        store = InMemoryVadResultStore()
        store.merge_range_result(
            media_path="demo.wav",
            engine_key="silero",
            duration_sec=100.0,
            time_range=VadTimeRange(0.0, 40.0),
            speech_segments=[
                SpeechSegment(5.0, 12.0),
                SpeechSegment(20.0, 32.0),
            ],
        )

        result = store.merge_range_result(
            media_path="demo.wav",
            engine_key="silero",
            duration_sec=100.0,
            time_range=VadTimeRange(10.0, 25.0),
            speech_segments=[
                SpeechSegment(11.0, 14.0),
                SpeechSegment(18.0, 22.0),
            ],
        )

        self.assertEqual(
            [(seg.start_sec, seg.end_sec) for seg in result.speech_segments],
            [(5.0, 10.0), (11.0, 14.0), (18.0, 22.0), (25.0, 32.0)],
        )
        self.assertEqual(
            [(item.start_sec, item.end_sec) for item in result.covered_ranges],
            [(0.0, 40.0)],
        )

    def test_merge_range_coalesces_touching_segments_and_ranges(self):
        store = InMemoryVadResultStore()
        store.merge_range_result(
            media_path="demo.wav",
            engine_key="silero",
            duration_sec=60.0,
            time_range=VadTimeRange(0.0, 10.0),
            speech_segments=[
                SpeechSegment(1.0, 2.0),
                SpeechSegment(2.0, 3.0),
            ],
        )
        result = store.merge_range_result(
            media_path="demo.wav",
            engine_key="silero",
            duration_sec=60.0,
            time_range=VadTimeRange(10.0, 20.0),
            speech_segments=[SpeechSegment(10.0, 12.0)],
        )

        self.assertEqual(
            [(seg.start_sec, seg.end_sec) for seg in result.speech_segments],
            [(1.0, 3.0), (10.0, 12.0)],
        )
        self.assertEqual(
            [(item.start_sec, item.end_sec) for item in result.covered_ranges],
            [(0.0, 20.0)],
        )


if __name__ == "__main__":
    unittest.main()
