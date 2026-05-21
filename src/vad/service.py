from __future__ import annotations

import math
from typing import Callable, Optional

from src.vad_exp.audio_strength_extractor import (
    extract_audio_strength_range_series,
    extract_audio_strength_series,
    strength_bin_count,
)

from .models import AudioStrengthPatch, VadAnalysisOutput, VadAnalysisRequest, VadTimeRange
from .ports import VadEnginePort
from .store import InMemoryVadResultStore


class VadApplicationService:
    """Coordinates amplitude extraction, VAD engines, and in-memory result merging.

    See `doc/vad-engine-silero-integration.md` for the current architecture
    snapshot and the expected extension points for adding more engines.
    """

    def __init__(self, engines: list[VadEnginePort], store: InMemoryVadResultStore | None = None):
        if not engines:
            raise ValueError("at least one VAD engine is required")
        self._engines = {engine.engine_key: engine for engine in engines}
        self._store = store or InMemoryVadResultStore()

    @property
    def store(self) -> InMemoryVadResultStore:
        return self._store

    def get_cached_result(self, media_path: str, engine_key: str):
        return self._store.get_result(media_path, engine_key)

    def request_analysis(
        self,
        request: VadAnalysisRequest,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> VadAnalysisOutput:
        output = VadAnalysisOutput()

        if request.include_amplitude:
            if _is_full_media_range(request):
                output.amplitude_series = extract_audio_strength_series(
                    media_path=request.media_path,
                    duration_sec=request.media_duration_sec,
                    points_per_second=request.amplitude_points_per_second,
                    sample_rate=request.amplitude_sample_rate,
                    should_stop=should_stop,
                )
                if output.amplitude_series is not None:
                    try:
                        output.amplitude_peak = float(output.amplitude_series.max())
                    except Exception:
                        output.amplitude_peak = None
            else:
                output.amplitude_patch = _extract_strength_patch(request, should_stop)
                if output.amplitude_patch is not None:
                    try:
                        output.amplitude_peak = float(output.amplitude_patch.values.max())
                    except Exception:
                        output.amplitude_peak = None

        if request.include_vad:
            engine = self._engines.get(request.engine_key)
            if engine is None:
                raise KeyError(f"unknown VAD engine: {request.engine_key}")

            analyzed_segments = engine.analyze_range(
                media_path=request.media_path,
                time_range=request.time_range,
                media_duration_sec=request.media_duration_sec,
                should_stop=should_stop,
            )
            output.analyzed_segments = analyzed_segments
            output.vad_result = self._store.merge_range_result(
                media_path=request.media_path,
                engine_key=request.engine_key,
                duration_sec=request.media_duration_sec,
                time_range=request.time_range,
                speech_segments=analyzed_segments,
            )
        else:
            output.vad_result = self._store.get_result(request.media_path, request.engine_key)

        output.status_message = _build_status_message(request)
        return output


def _build_status_message(request: VadAnalysisRequest) -> str:
    if request.include_amplitude and request.include_vad:
        return f"Amplitude + {request.engine_key} VAD ready"
    if request.include_amplitude:
        return "Amplitude ready"
    return f"{request.engine_key} VAD ready"


def _is_full_media_range(request: VadAnalysisRequest) -> bool:
    return (
        request.time_range.start_sec <= 0.0
        and request.time_range.end_sec >= request.media_duration_sec
    )


def _extract_strength_patch(request: VadAnalysisRequest, should_stop=None) -> AudioStrengthPatch | None:
    points_per_second = request.amplitude_points_per_second
    start_index = max(int(math.floor(request.time_range.start_sec * points_per_second)), 0)
    total_bins = strength_bin_count(request.media_duration_sec, points_per_second)
    end_index = min(int(math.ceil(request.time_range.end_sec * points_per_second)), total_bins)
    if end_index <= start_index:
        return None

    aligned_range = VadTimeRange(
        start_sec=start_index / points_per_second,
        end_sec=min(end_index / points_per_second, request.media_duration_sec),
    )
    values = extract_audio_strength_range_series(
        media_path=request.media_path,
        time_range=aligned_range,
        points_per_second=points_per_second,
        sample_rate=request.amplitude_sample_rate,
        should_stop=should_stop,
        normalize=False,
    )
    if len(values) == 0:
        return None
    return AudioStrengthPatch(
        time_range=aligned_range,
        start_index=start_index,
        values=values,
    )
