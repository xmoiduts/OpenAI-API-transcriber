from __future__ import annotations

from typing import Callable, Optional

from src.vad_exp.audio_strength_extractor import extract_audio_strength_series

from .models import VadAnalysisOutput, VadAnalysisRequest
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
