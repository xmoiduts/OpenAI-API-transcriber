from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


EPSILON = 1e-6


class VadProcessingCancelled(Exception):
    """Raised when a VAD-related analysis task is cancelled."""


@dataclass(frozen=True)
class VadTimeRange:
    start_sec: float
    end_sec: float

    def __post_init__(self):
        start = float(self.start_sec)
        end = float(self.end_sec)
        if end <= start:
            raise ValueError("end_sec must be greater than start_sec")
        object.__setattr__(self, "start_sec", start)
        object.__setattr__(self, "end_sec", end)

    @property
    def duration_sec(self) -> float:
        return self.end_sec - self.start_sec

    def overlaps(self, other: "VadTimeRange") -> bool:
        return self.start_sec < other.end_sec and other.start_sec < self.end_sec

    def touches(self, other: "VadTimeRange", epsilon: float = EPSILON) -> bool:
        return abs(self.end_sec - other.start_sec) <= epsilon or abs(other.end_sec - self.start_sec) <= epsilon

    def clamp(self, min_start: float, max_end: float) -> "VadTimeRange":
        start = max(float(min_start), self.start_sec)
        end = min(float(max_end), self.end_sec)
        if end <= start:
            raise ValueError("clamped range is empty")
        return VadTimeRange(start_sec=start, end_sec=end)


@dataclass(frozen=True)
class SpeechSegment:
    start_sec: float
    end_sec: float
    score: Optional[float] = None
    source_range: Optional[VadTimeRange] = None

    def __post_init__(self):
        start = float(self.start_sec)
        end = float(self.end_sec)
        if end <= start:
            raise ValueError("segment end_sec must be greater than start_sec")
        object.__setattr__(self, "start_sec", start)
        object.__setattr__(self, "end_sec", end)
        if self.score is not None:
            object.__setattr__(self, "score", float(self.score))

    def clamp(self, time_range: VadTimeRange) -> Optional["SpeechSegment"]:
        start = max(self.start_sec, time_range.start_sec)
        end = min(self.end_sec, time_range.end_sec)
        if end <= start:
            return None
        return SpeechSegment(
            start_sec=start,
            end_sec=end,
            score=self.score,
            source_range=self.source_range,
        )


@dataclass
class VadAnalysisResult:
    media_path: str
    engine_key: str
    duration_sec: float
    covered_ranges: list[VadTimeRange] = field(default_factory=list)
    speech_segments: list[SpeechSegment] = field(default_factory=list)


@dataclass(frozen=True)
class VadAnalysisRequest:
    media_path: str
    time_range: VadTimeRange
    media_duration_sec: float
    engine_key: str = "silero"
    include_amplitude: bool = True
    include_vad: bool = True
    amplitude_points_per_second: int = 50
    amplitude_sample_rate: int = 8000

    def __post_init__(self):
        duration_sec = float(self.media_duration_sec)
        if duration_sec <= 0:
            raise ValueError("media_duration_sec must be positive")
        object.__setattr__(self, "media_duration_sec", duration_sec)
        if not (self.include_amplitude or self.include_vad):
            raise ValueError("at least one of include_amplitude/include_vad must be True")


@dataclass(frozen=True)
class AudioStrengthPatch:
    time_range: VadTimeRange
    start_index: int
    values: object


@dataclass
class VadPartialAnalysisOutput:
    amplitude_patch: Optional[AudioStrengthPatch] = None
    amplitude_peak: float | None = None
    vad_result: Optional[VadAnalysisResult] = None
    processed_ranges: list[VadTimeRange] = field(default_factory=list)
    active_ranges: list[VadTimeRange] = field(default_factory=list)
    status_message: str = ""


@dataclass
class VadAnalysisOutput:
    amplitude_series: object | None = None
    amplitude_patch: Optional[AudioStrengthPatch] = None
    amplitude_peak: float | None = None
    vad_result: Optional[VadAnalysisResult] = None
    analyzed_segments: list[SpeechSegment] = field(default_factory=list)
    status_message: str = ""
