from PyQt5.QtCore import QThread, pyqtSignal

from src.vad_exp.audio_strength_extractor import (
    AudioStrengthExtractionCancelled,
    extract_audio_strength_series,
)


class AudioParseThread(QThread):
    """Background worker that extracts timeline-ready audio strength bins."""

    success = pyqtSignal(int, object)  # generation, np.ndarray
    failed = pyqtSignal(int, str)
    cancelled = pyqtSignal(int)

    def __init__(self, generation: int, media_path: str, duration_sec: float, parent=None):
        super().__init__(parent)
        self.generation = generation
        self.media_path = media_path
        self.duration_sec = duration_sec
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def run(self):
        try:
            series = extract_audio_strength_series(
                media_path=self.media_path,
                duration_sec=self.duration_sec,
                points_per_second=50,
                sample_rate=8000,
                should_stop=lambda: self._stop_requested,
            )
        except AudioStrengthExtractionCancelled:
            self.cancelled.emit(self.generation)
            return
        except Exception as exc:
            self.failed.emit(self.generation, str(exc))
            return

        if self._stop_requested:
            self.cancelled.emit(self.generation)
            return

        self.success.emit(self.generation, series)
