from __future__ import annotations

from copy import deepcopy

from .models import EPSILON, SpeechSegment, VadAnalysisResult, VadTimeRange


class InMemoryVadResultStore:
    """Keeps per-media, per-engine VAD results in memory only."""

    def __init__(self):
        self._results: dict[tuple[str, str], VadAnalysisResult] = {}

    def clear(self):
        self._results.clear()

    def get_result(self, media_path: str, engine_key: str) -> VadAnalysisResult | None:
        result = self._results.get((media_path, engine_key))
        if result is None:
            return None
        return deepcopy(result)

    def set_result(self, result: VadAnalysisResult):
        self._results[(result.media_path, result.engine_key)] = deepcopy(result)

    def merge_range_result(
        self,
        media_path: str,
        engine_key: str,
        duration_sec: float,
        time_range: VadTimeRange,
        speech_segments: list[SpeechSegment],
    ) -> VadAnalysisResult:
        key = (media_path, engine_key)
        current = self._results.get(key)
        if current is None:
            current = VadAnalysisResult(
                media_path=media_path,
                engine_key=engine_key,
                duration_sec=float(duration_sec),
            )

        clamped_range = time_range.clamp(0.0, float(duration_sec))
        normalized_segments = _normalize_segments(speech_segments, clamped_range)
        replaced_segments = _replace_range_segments(current.speech_segments, clamped_range, normalized_segments)
        covered_ranges = _merge_time_ranges([*current.covered_ranges, clamped_range])

        merged = VadAnalysisResult(
            media_path=media_path,
            engine_key=engine_key,
            duration_sec=float(duration_sec),
            covered_ranges=covered_ranges,
            speech_segments=replaced_segments,
        )
        self._results[key] = merged
        return deepcopy(merged)


def _normalize_segments(
    speech_segments: list[SpeechSegment],
    time_range: VadTimeRange,
) -> list[SpeechSegment]:
    normalized = []
    for segment in speech_segments:
        clamped = segment.clamp(time_range)
        if clamped is not None:
            normalized.append(clamped)
    return _merge_touching_segments(normalized)


def _replace_range_segments(
    existing_segments: list[SpeechSegment],
    replacement_range: VadTimeRange,
    new_segments: list[SpeechSegment],
) -> list[SpeechSegment]:
    preserved_segments: list[SpeechSegment] = []
    for segment in existing_segments:
        if segment.end_sec <= replacement_range.start_sec or segment.start_sec >= replacement_range.end_sec:
            preserved_segments.append(segment)
            continue

        if segment.start_sec < replacement_range.start_sec:
            preserved_segments.append(
                SpeechSegment(
                    start_sec=segment.start_sec,
                    end_sec=replacement_range.start_sec,
                    score=segment.score,
                    source_range=segment.source_range,
                )
            )

        if segment.end_sec > replacement_range.end_sec:
            preserved_segments.append(
                SpeechSegment(
                    start_sec=replacement_range.end_sec,
                    end_sec=segment.end_sec,
                    score=segment.score,
                    source_range=segment.source_range,
                )
            )

    return _merge_touching_segments([*preserved_segments, *new_segments])


def _merge_time_ranges(ranges: list[VadTimeRange]) -> list[VadTimeRange]:
    if not ranges:
        return []

    sorted_ranges = sorted(ranges, key=lambda item: (item.start_sec, item.end_sec))
    merged = [sorted_ranges[0]]
    for current in sorted_ranges[1:]:
        previous = merged[-1]
        if previous.overlaps(current) or previous.touches(current):
            merged[-1] = VadTimeRange(
                start_sec=min(previous.start_sec, current.start_sec),
                end_sec=max(previous.end_sec, current.end_sec),
            )
            continue
        merged.append(current)
    return merged


def _merge_touching_segments(segments: list[SpeechSegment]) -> list[SpeechSegment]:
    if not segments:
        return []

    sorted_segments = sorted(segments, key=lambda item: (item.start_sec, item.end_sec))
    merged = [sorted_segments[0]]
    for current in sorted_segments[1:]:
        previous = merged[-1]
        if current.start_sec <= previous.end_sec + EPSILON:
            merged[-1] = SpeechSegment(
                start_sec=previous.start_sec,
                end_sec=max(previous.end_sec, current.end_sec),
                score=_merge_score(previous.score, current.score),
                source_range=current.source_range or previous.source_range,
            )
            continue
        merged.append(current)
    return merged


def _merge_score(left: float | None, right: float | None) -> float | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)
