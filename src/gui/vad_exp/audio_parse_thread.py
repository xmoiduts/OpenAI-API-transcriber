from PyQt5.QtCore import QThread, pyqtSignal

from src.vad.models import VadAnalysisRequest, VadProcessingCancelled, VadTimeRange
from src.vad.coordinator import ChunkedVadCoordinator, ParallelVadConfig
from src.vad.service import VadApplicationService
from src.vad_exp.audio_strength_extractor import AudioStrengthExtractionCancelled


class AudioParseThread(QThread):
    """Background worker for amplitude and/or VAD analysis.

    The intended request modes and engine layering are documented in
    `doc/vad-engine-silero-integration.md`.
    """

    success = pyqtSignal(int, object)  # generation, VadAnalysisOutput
    partial_update = pyqtSignal(int, object)  # generation, VadPartialAnalysisOutput
    failed = pyqtSignal(int, str)
    cancelled = pyqtSignal(int)

    def __init__(
        self,
        generation: int,
        media_path: str,
        duration_sec: float,
        service: VadApplicationService,
        start_sec: float = 0.0,
        end_sec: float | None = None,
        include_amplitude: bool = True,
        include_vad: bool = True,
        engine_key: str = "silero",
        parallel_config: ParallelVadConfig | None = None,
        engine_factory=None,
        parent=None,
    ):
        super().__init__(parent)
        self.generation = generation
        self.media_path = media_path
        self.duration_sec = duration_sec
        self.service = service
        self.start_sec = start_sec
        self.end_sec = duration_sec if end_sec is None else end_sec
        self.include_amplitude = include_amplitude
        self.include_vad = include_vad
        self.engine_key = engine_key
        self.parallel_config = parallel_config
        self.engine_factory = engine_factory
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def run(self):
        request = VadAnalysisRequest(
            media_path=self.media_path,
            time_range=VadTimeRange(self.start_sec, self.end_sec),
            media_duration_sec=self.duration_sec,
            engine_key=self.engine_key,
            include_amplitude=self.include_amplitude,
            include_vad=self.include_vad,
        )
        try:
            if (
                self.parallel_config is not None
                and self.engine_factory is not None
                and ChunkedVadCoordinator.should_use_parallel(request, self.parallel_config)
            ):
                coordinator = ChunkedVadCoordinator(
                    engine_factory=self.engine_factory,
                    final_store=self.service.store,
                )
                result = coordinator.run(
                    request=request,
                    config=self.parallel_config,
                    should_stop=lambda: self._stop_requested,
                    on_partial_update=lambda update: self.partial_update.emit(self.generation, update),
                )
            else:
                result = self.service.request_analysis(
                    request,
                    should_stop=lambda: self._stop_requested,
                )
        except (AudioStrengthExtractionCancelled, VadProcessingCancelled):
            self.cancelled.emit(self.generation)
            return
        except Exception as exc:
            self.failed.emit(self.generation, str(exc))
            return

        if self._stop_requested:
            self.cancelled.emit(self.generation)
            return

        self.success.emit(self.generation, result)
