from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Optional

from .models import SpeechSegment, VadTimeRange


class VadEnginePort(ABC):
    """Business-facing VAD engine interface."""

    @property
    @abstractmethod
    def engine_key(self) -> str:
        """Stable engine identifier."""

    @abstractmethod
    def analyze_range(
        self,
        media_path: str,
        time_range: VadTimeRange,
        media_duration_sec: float,
        should_stop: Optional[Callable[[], bool]] = None,
    ) -> list[SpeechSegment]:
        """Analyze one time range and return normalized speech segments."""
