from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .models import AudioStrengthPatch, SpeechSegment, VadTimeRange


@dataclass(frozen=True)
class SliceLengthPreset:
    label: str
    seconds: int
    limit_mode: str
    lookbehind_seconds: int
    lookahead_seconds: int

    @property
    def is_hard_limit(self) -> bool:
        return self.limit_mode == "hard"


SLICE_LENGTH_PRESETS = {
    "~10min": SliceLengthPreset("~10min", 600, "soft", 60, 60),
    "<3min": SliceLengthPreset("<3min", 180, "hard", 60, 0),
    "<1min": SliceLengthPreset("<1min", 60, "hard", 30, 0),
    "<30s": SliceLengthPreset("<30s", 30, "hard", 30, 0),
}


def get_slice_length_preset(label: str) -> SliceLengthPreset:
    return SLICE_LENGTH_PRESETS.get(label, SLICE_LENGTH_PRESETS["~10min"])


def build_probe_range(base_sec: float, duration_sec: float, preset: SliceLengthPreset) -> VadTimeRange:
    base_sec = max(float(base_sec), 0.0)
    duration_sec = max(float(duration_sec), 1.0)
    target_sec = min(base_sec + preset.seconds, duration_sec)
    start_sec = max(base_sec, target_sec - preset.lookbehind_seconds)
    end_sec = min(duration_sec, target_sec + preset.lookahead_seconds)
    if end_sec <= start_sec:
        end_sec = min(duration_sec, start_sec + 1.0)
    if end_sec <= start_sec:
        start_sec = max(0.0, duration_sec - 1.0)
        end_sec = duration_sec
    return VadTimeRange(start_sec, end_sec)


def choose_auto_cut_point(
    base_sec: float,
    duration_sec: float,
    preset: SliceLengthPreset,
    speech_segments: list[SpeechSegment],
    strength_patch: AudioStrengthPatch | None = None,
    min_silence_sec: float = 0.8,
) -> float:
    target_sec = min(max(float(base_sec), 0.0) + preset.seconds, float(duration_sec))
    probe_range = build_probe_range(base_sec, duration_sec, preset)
    gaps = _silence_gaps(probe_range, speech_segments)
    candidates = []
    for gap_start, gap_end in gaps:
        gap_duration = gap_end - gap_start
        if gap_duration < min_silence_sec:
            continue
        candidate = _candidate_from_gap(gap_start, gap_end)
        if preset.is_hard_limit:
            candidate = min(candidate, target_sec)
        candidates.append((abs(candidate - target_sec), -gap_duration, candidate))

    if candidates:
        # Prefer the silence nearest the desired slice target, then the longer
        # silence gap. Long gaps bias rightward so the next slice reaches speech quickly.
        candidates.sort()
        return _clamp(candidates[0][2], float(base_sec) + 1.0, float(duration_sec))

    fallback = _lowest_strength_time(strength_patch, probe_range)
    if fallback is not None:
        if preset.is_hard_limit:
            fallback = min(fallback, target_sec)
        return _clamp(fallback, float(base_sec) + 1.0, float(duration_sec))

    return _clamp(target_sec, float(base_sec) + 1.0, float(duration_sec))


def _silence_gaps(
    probe_range: VadTimeRange,
    speech_segments: list[SpeechSegment],
) -> list[tuple[float, float]]:
    clipped_segments = []
    for segment in sorted(speech_segments, key=lambda item: (item.start_sec, item.end_sec)):
        if segment.end_sec <= probe_range.start_sec or segment.start_sec >= probe_range.end_sec:
            continue
        clipped_segments.append(
            (
                max(segment.start_sec, probe_range.start_sec),
                min(segment.end_sec, probe_range.end_sec),
            )
        )

    gaps = []
    cursor = probe_range.start_sec
    for start_sec, end_sec in clipped_segments:
        if start_sec > cursor:
            gaps.append((cursor, start_sec))
        cursor = max(cursor, end_sec)
    if cursor < probe_range.end_sec:
        gaps.append((cursor, probe_range.end_sec))
    return gaps


def _candidate_from_gap(gap_start: float, gap_end: float) -> float:
    if gap_end - gap_start < 6.0:
        return (gap_start + gap_end) / 2.0
    return max((gap_start + gap_end) / 2.0, gap_end - 3.0)


def _lowest_strength_time(
    strength_patch: AudioStrengthPatch | None,
    probe_range: VadTimeRange,
) -> float | None:
    if strength_patch is None:
        return None
    values = np.asarray(strength_patch.values)
    if values.size == 0 or strength_patch.time_range.duration_sec <= 0:
        return None

    points_per_second = values.size / strength_patch.time_range.duration_sec
    start_index = max(int((probe_range.start_sec - strength_patch.time_range.start_sec) * points_per_second), 0)
    end_index = min(int((probe_range.end_sec - strength_patch.time_range.start_sec) * points_per_second), values.size)
    if end_index <= start_index:
        return None

    local_index = int(np.argmin(values[start_index:end_index]))
    absolute_index = start_index + local_index
    return strength_patch.time_range.start_sec + (absolute_index / points_per_second)


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(float(min_value), min(float(value), float(max_value)))
