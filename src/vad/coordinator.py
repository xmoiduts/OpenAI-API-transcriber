from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from threading import Event, Lock
from typing import Callable, Optional

import numpy as np

from src.vad.models import (
    AudioStrengthPatch,
    EPSILON,
    SpeechSegment,
    VadAnalysisOutput,
    VadAnalysisRequest,
    VadPartialAnalysisOutput,
    VadProcessingCancelled,
    VadTimeRange,
)
from src.vad.store import InMemoryVadResultStore
from src.vad_exp.audio_strength_extractor import (
    AudioStrengthExtractionCancelled,
    extract_audio_strength_range_series,
    strength_bin_count,
)


@dataclass(frozen=True)
class ParallelVadConfig:
    parallel_workers: int = 4
    slice_minutes: int = 2
    parallel_min_duration_seconds: int = 900

    def __post_init__(self):
        if int(self.parallel_workers) <= 0:
            raise ValueError("parallel_workers must be positive")
        if int(self.slice_minutes) <= 0:
            raise ValueError("slice_minutes must be positive")
        if int(self.parallel_min_duration_seconds) < 0:
            raise ValueError("parallel_min_duration_seconds cannot be negative")

    @property
    def slice_duration_sec(self) -> float:
        return float(self.slice_minutes) * 60.0


@dataclass(frozen=True)
class _AlignedStrengthPatchRange:
    time_range: VadTimeRange
    start_index: int


class ChunkedVadCoordinator:
    """Coordinate parallel worker probing, chunked VAD, and incremental UI updates."""

    def __init__(
        self,
        engine_factory: Callable[[], object],
        final_store: InMemoryVadResultStore | None = None,
    ):
        self._engine_factory = engine_factory
        self._final_store = final_store

    @staticmethod
    def should_use_parallel(request: VadAnalysisRequest, config: ParallelVadConfig) -> bool:
        if not (request.include_amplitude and request.include_vad):
            return False
        if request.time_range.duration_sec < float(config.parallel_min_duration_seconds):
            return False
        max_workers = min(
            int(config.parallel_workers),
            max(int(request.time_range.duration_sec // max(config.slice_duration_sec, 1.0)), 1),
        )
        return max_workers >= 2

    def run(
        self,
        request: VadAnalysisRequest,
        config: ParallelVadConfig,
        should_stop: Optional[Callable[[], bool]] = None,
        on_partial_update: Optional[Callable[[VadPartialAnalysisOutput], None]] = None,
    ) -> VadAnalysisOutput:
        if not self.should_use_parallel(request, config):
            raise ValueError("parallel coordinator requires a long amplitude + VAD request")

        self._request = request
        self._config = config
        self._should_stop = should_stop
        self._on_partial_update = on_partial_update
        self._abort_event = Event()
        self._state_lock = Lock()
        self._active_ranges: list[VadTimeRange] = []
        self._processed_ranges: list[VadTimeRange] = []
        total_bins = strength_bin_count(request.media_duration_sec, request.amplitude_points_per_second)
        self._strength_series = np.zeros(total_bins, dtype=np.float32)
        self._strength_peak = 0.0
        self._local_store = InMemoryVadResultStore()

        worker_count = min(
            int(config.parallel_workers),
            max(int(request.time_range.duration_sec // max(config.slice_duration_sec, 1.0)), 1),
        )
        worker_starts = self._probe_worker_starts(worker_count)
        worker_ranges = [
            VadTimeRange(start_sec=start_sec, end_sec=end_sec)
            for start_sec, end_sec in zip(worker_starts, [*worker_starts[1:], request.time_range.end_sec])
            if end_sec - start_sec > EPSILON
        ]

        with ThreadPoolExecutor(max_workers=max(len(worker_ranges), 1)) as executor:
            futures = [
                executor.submit(self._run_worker, worker_index, worker_range)
                for worker_index, worker_range in enumerate(worker_ranges)
            ]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception:
                    self._abort_event.set()
                    raise

        final_vad_result = None
        if request.include_vad:
            final_vad_result = self._local_store.get_result(request.media_path, request.engine_key)
            if final_vad_result is not None and self._final_store is not None:
                self._final_store.set_result(final_vad_result)

        final_peak = self._strength_peak if request.include_amplitude else None
        return VadAnalysisOutput(
            amplitude_series=self._strength_series.copy() if request.include_amplitude else None,
            amplitude_peak=final_peak,
            vad_result=final_vad_result,
            status_message=self._build_ready_message(),
        )

    def _probe_worker_starts(self, worker_count: int) -> list[float]:
        starts = {0: self._request.time_range.start_sec}
        nominal_starts = [
            self._request.time_range.start_sec + (self._request.time_range.duration_sec * index / worker_count)
            for index in range(worker_count)
        ]

        if worker_count <= 1:
            return [starts[0]]

        with ThreadPoolExecutor(max_workers=max(worker_count - 1, 1)) as executor:
            futures = {
                executor.submit(self._probe_worker_start, nominal_starts[index]): index
                for index in range(1, worker_count)
            }
            for future in as_completed(futures):
                index = futures[future]
                try:
                    starts[index] = future.result()
                except Exception:
                    self._abort_event.set()
                    raise

        return [starts[index] for index in range(worker_count)]

    def _probe_worker_start(self, nominal_start_sec: float) -> float:
        engine = self._engine_factory()
        cursor = float(nominal_start_sec)
        request_end = self._request.time_range.end_sec
        slice_duration_sec = self._config.slice_duration_sec

        while cursor < request_end - EPSILON:
            self._raise_if_stopped()
            probe_end = min(cursor + slice_duration_sec, request_end)
            probe_range = VadTimeRange(cursor, probe_end)
            self._push_active_range(probe_range, emit=True)
            try:
                segments = engine.analyze_range(
                    media_path=self._request.media_path,
                    time_range=probe_range,
                    media_duration_sec=self._request.media_duration_sec,
                    should_stop=self._effective_should_stop,
                )
            finally:
                self._pop_active_range(probe_range, emit=True)

            if not segments:
                return cursor

            first_segment = segments[0]
            if first_segment.start_sec > cursor + EPSILON:
                return first_segment.start_sec

            for segment in segments[1:]:
                if segment.start_sec > cursor + EPSILON:
                    return segment.start_sec

            cursor = probe_end

        return request_end

    def _run_worker(self, worker_index: int, worker_range: VadTimeRange):
        engine = self._engine_factory()
        cursor = worker_range.start_sec
        slice_duration_sec = self._config.slice_duration_sec

        while cursor < worker_range.end_sec - EPSILON:
            self._raise_if_stopped()
            window_end = min(cursor + slice_duration_sec, worker_range.end_sec)
            analysis_range = VadTimeRange(cursor, window_end)
            self._push_active_range(analysis_range, emit=True)
            try:
                segments = engine.analyze_range(
                    media_path=self._request.media_path,
                    time_range=analysis_range,
                    media_duration_sec=self._request.media_duration_sec,
                    should_stop=self._effective_should_stop,
                )
                confirmed_range, confirmed_segments, next_cursor = self._resolve_slice_result(
                    analysis_range=analysis_range,
                    worker_range=worker_range,
                    speech_segments=segments,
                )
                strength_patch = self._build_strength_patch(confirmed_range)
            finally:
                self._pop_active_range(analysis_range, emit=False)

            self._merge_confirmed_result(
                worker_index=worker_index,
                confirmed_range=confirmed_range,
                confirmed_segments=confirmed_segments,
                strength_patch=strength_patch,
            )
            cursor = next_cursor

    def _resolve_slice_result(
        self,
        analysis_range: VadTimeRange,
        worker_range: VadTimeRange,
        speech_segments: list[SpeechSegment],
    ) -> tuple[VadTimeRange, list[SpeechSegment], float]:
        is_final_window = analysis_range.end_sec >= worker_range.end_sec - EPSILON
        if is_final_window or not speech_segments:
            return analysis_range, list(speech_segments), analysis_range.end_sec

        last_segment = speech_segments[-1]
        if last_segment.start_sec > analysis_range.start_sec + EPSILON:
            confirmed_end = min(last_segment.start_sec, worker_range.end_sec)
            if confirmed_end > analysis_range.start_sec + EPSILON:
                confirmed_range = VadTimeRange(analysis_range.start_sec, confirmed_end)
                return confirmed_range, list(speech_segments[:-1]), confirmed_end

        # When a very long speech block begins exactly at the slice start, rewinding
        # to `c_start` would stall forever. Keep the whole slice and move forward.
        return analysis_range, list(speech_segments), analysis_range.end_sec

    def _build_strength_patch(self, confirmed_range: VadTimeRange) -> AudioStrengthPatch | None:
        aligned_patch = _align_strength_patch_range(
            time_range=confirmed_range,
            media_duration_sec=self._request.media_duration_sec,
            points_per_second=self._request.amplitude_points_per_second,
        )
        if aligned_patch is None:
            return None

        values = extract_audio_strength_range_series(
            media_path=self._request.media_path,
            time_range=aligned_patch.time_range,
            points_per_second=self._request.amplitude_points_per_second,
            sample_rate=self._request.amplitude_sample_rate,
            should_stop=self._effective_should_stop,
            normalize=False,
        )
        if len(values) == 0:
            return None

        patch_time_range = VadTimeRange(
            aligned_patch.time_range.start_sec,
            min(
                aligned_patch.time_range.start_sec + (len(values) / self._request.amplitude_points_per_second),
                self._request.media_duration_sec,
            ),
        )
        return AudioStrengthPatch(
            time_range=patch_time_range,
            start_index=aligned_patch.start_index,
            values=np.asarray(values, dtype=np.float32),
        )

    def _merge_confirmed_result(
        self,
        worker_index: int,
        confirmed_range: VadTimeRange,
        confirmed_segments: list[SpeechSegment],
        strength_patch: AudioStrengthPatch | None,
    ):
        with self._state_lock:
            if strength_patch is not None:
                patch_values = np.asarray(strength_patch.values, dtype=np.float32)
                start_index = max(int(strength_patch.start_index), 0)
                end_index = min(start_index + len(patch_values), len(self._strength_series))
                if end_index > start_index:
                    actual_values = patch_values[:end_index - start_index]
                    self._strength_series[start_index:end_index] = actual_values
                    if actual_values.size > 0:
                        self._strength_peak = max(self._strength_peak, float(np.max(actual_values)))
                    adjusted_time_range = VadTimeRange(
                        strength_patch.time_range.start_sec,
                        min(
                            strength_patch.time_range.start_sec
                            + (len(actual_values) / self._request.amplitude_points_per_second),
                            self._request.media_duration_sec,
                        ),
                    )
                    if adjusted_time_range.duration_sec > EPSILON:
                        self._processed_ranges = _merge_ranges([*self._processed_ranges, adjusted_time_range])
                        strength_patch = AudioStrengthPatch(
                            time_range=adjusted_time_range,
                            start_index=start_index,
                            values=actual_values.copy(),
                        )
                    else:
                        strength_patch = None
                else:
                    strength_patch = None

            vad_result = self._local_store.merge_range_result(
                media_path=self._request.media_path,
                engine_key=self._request.engine_key,
                duration_sec=self._request.media_duration_sec,
                time_range=confirmed_range,
                speech_segments=confirmed_segments,
            )
            active_ranges = list(self._active_ranges)
            processed_ranges = list(self._processed_ranges)

        self._emit_partial_update(
            VadPartialAnalysisOutput(
                amplitude_patch=strength_patch,
                amplitude_peak=self._strength_peak if self._request.include_amplitude else None,
                vad_result=vad_result,
                processed_ranges=processed_ranges,
                active_ranges=active_ranges,
                status_message=self._build_progress_message(worker_index, processed_ranges, active_ranges),
            )
        )

    def _push_active_range(self, time_range: VadTimeRange, emit: bool):
        with self._state_lock:
            self._active_ranges.append(time_range)
            active_ranges = list(self._active_ranges)
            processed_ranges = list(self._processed_ranges)
            vad_result = self._local_store.get_result(self._request.media_path, self._request.engine_key)
        if emit:
            self._emit_partial_update(
                VadPartialAnalysisOutput(
                    amplitude_peak=self._strength_peak if self._request.include_amplitude else None,
                    vad_result=vad_result,
                    processed_ranges=processed_ranges,
                    active_ranges=active_ranges,
                    status_message=self._build_probe_message(processed_ranges, active_ranges),
                )
            )

    def _pop_active_range(self, time_range: VadTimeRange, emit: bool):
        with self._state_lock:
            self._active_ranges = [
                item for item in self._active_ranges
                if not (
                    abs(item.start_sec - time_range.start_sec) <= EPSILON
                    and abs(item.end_sec - time_range.end_sec) <= EPSILON
                )
            ]
            active_ranges = list(self._active_ranges)
            processed_ranges = list(self._processed_ranges)
            vad_result = self._local_store.get_result(self._request.media_path, self._request.engine_key)
        if emit:
            self._emit_partial_update(
                VadPartialAnalysisOutput(
                    amplitude_peak=self._strength_peak if self._request.include_amplitude else None,
                    vad_result=vad_result,
                    processed_ranges=processed_ranges,
                    active_ranges=active_ranges,
                    status_message=self._build_probe_message(processed_ranges, active_ranges),
                )
            )

    def _emit_partial_update(self, update: VadPartialAnalysisOutput):
        if self._on_partial_update is not None:
            self._on_partial_update(update)

    def _build_probe_message(
        self,
        processed_ranges: list[VadTimeRange],
        active_ranges: list[VadTimeRange],
    ) -> str:
        progress_percent = _covered_ratio(processed_ranges, self._request.time_range) * 100.0
        if active_ranges:
            return f"Discovering worker boundaries... {progress_percent:.1f}% confirmed"
        return f"Worker boundaries ready. {progress_percent:.1f}% confirmed"

    def _build_progress_message(
        self,
        worker_index: int,
        processed_ranges: list[VadTimeRange],
        active_ranges: list[VadTimeRange],
    ) -> str:
        progress_percent = _covered_ratio(processed_ranges, self._request.time_range) * 100.0
        if active_ranges:
            return (
                f"Running chunked amplitude + {self._request.engine_key} VAD "
                f"(worker {worker_index + 1})... {progress_percent:.1f}% confirmed"
            )
        return f"Chunked amplitude + {self._request.engine_key} VAD ready"

    def _build_ready_message(self) -> str:
        return f"Chunked amplitude + {self._request.engine_key} VAD ready"

    def _raise_if_stopped(self):
        if self._effective_should_stop():
            raise VadProcessingCancelled()

    def _effective_should_stop(self) -> bool:
        return self._abort_event.is_set() or (
            self._should_stop is not None and self._should_stop()
        )


def _align_strength_patch_range(
    time_range: VadTimeRange,
    media_duration_sec: float,
    points_per_second: int,
) -> _AlignedStrengthPatchRange | None:
    start_index = max(int(math.floor(time_range.start_sec * points_per_second)), 0)
    total_bins = strength_bin_count(media_duration_sec, points_per_second)
    end_index = min(int(math.ceil(time_range.end_sec * points_per_second)), total_bins)
    if end_index <= start_index:
        return None

    range_start_sec = start_index / points_per_second
    range_end_sec = min(end_index / points_per_second, media_duration_sec)
    if range_end_sec <= range_start_sec:
        return None

    return _AlignedStrengthPatchRange(
        time_range=VadTimeRange(range_start_sec, range_end_sec),
        start_index=start_index,
    )


def _covered_ratio(processed_ranges: list[VadTimeRange], total_range: VadTimeRange) -> float:
    if total_range.duration_sec <= EPSILON:
        return 1.0
    covered_sec = 0.0
    for item in processed_ranges:
        start_sec = max(item.start_sec, total_range.start_sec)
        end_sec = min(item.end_sec, total_range.end_sec)
        if end_sec > start_sec:
            covered_sec += end_sec - start_sec
    return max(0.0, min(covered_sec / total_range.duration_sec, 1.0))


def _merge_ranges(ranges: list[VadTimeRange]) -> list[VadTimeRange]:
    if not ranges:
        return []

    merged = [sorted(ranges, key=lambda item: (item.start_sec, item.end_sec))[0]]
    for current in sorted(ranges, key=lambda item: (item.start_sec, item.end_sec))[1:]:
        previous = merged[-1]
        if previous.overlaps(current) or previous.touches(current):
            merged[-1] = VadTimeRange(
                start_sec=min(previous.start_sec, current.start_sec),
                end_sec=max(previous.end_sec, current.end_sec),
            )
        else:
            merged.append(current)
    return merged
