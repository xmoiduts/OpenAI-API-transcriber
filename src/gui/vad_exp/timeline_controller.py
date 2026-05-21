import math

from PyQt5.QtCore import QObject, pyqtSignal


class TimelineController(QObject):
    """Shared viewport state for the experimental VAD timeline."""

    viewport_changed = pyqtSignal()
    scrollbar_state_changed = pyqtSignal(int, int, int)  # value, max, page step

    def __init__(self, duration_sec=7200.0, samples_per_second=50, pixels_per_sample=1, parent=None):
        super().__init__(parent)
        self.samples_per_second = samples_per_second
        self.pixels_per_sample = float(pixels_per_sample)
        self.duration_sec = max(float(duration_sec), 1.0)
        self.viewport_width_px = 1
        self.offset_px = 0
        self.min_pixels_per_sample = 0.1
        self.max_pixels_per_sample = 8.0

    @property
    def pixels_per_second(self) -> float:
        return self.samples_per_second * self.pixels_per_sample

    @property
    def total_width_px(self) -> int:
        return max(int(math.ceil(self.duration_sec * self.pixels_per_second)), 1)

    @property
    def max_offset_px(self) -> int:
        return max(self.total_width_px - self.viewport_width_px, 0)

    @property
    def visible_duration_sec(self) -> float:
        return self.viewport_width_px / max(self.pixels_per_second, 1)

    def set_duration(self, duration_sec: float):
        self.duration_sec = max(float(duration_sec), 1.0)
        self.set_offset_px(min(self.offset_px, self.max_offset_px), emit_viewport=False)
        self._emit_state_changed()

    def set_pixels_per_sample(self, pixels_per_sample: float, anchor_view_x: float | None = None):
        clamped = max(self.min_pixels_per_sample, min(float(pixels_per_sample), self.max_pixels_per_sample))
        if abs(clamped - self.pixels_per_sample) < 1e-6:
            return

        if anchor_view_x is None:
            anchor_view_x = self.viewport_width_px / 2

        anchor_time = self.view_x_to_time(anchor_view_x)
        self.pixels_per_sample = clamped
        new_offset = int(round(anchor_time * self.pixels_per_second - anchor_view_x))
        self.set_offset_px(new_offset, emit_viewport=False)
        self._emit_state_changed()

    def zoom_by_factor(self, factor: float, anchor_view_x: float | None = None):
        if factor <= 0:
            return
        self.set_pixels_per_sample(self.pixels_per_sample * float(factor), anchor_view_x)

    def set_viewport_width(self, width_px: int):
        width_px = max(int(width_px), 1)
        if width_px == self.viewport_width_px:
            return

        self.viewport_width_px = width_px
        self.set_offset_px(min(self.offset_px, self.max_offset_px), emit_viewport=False)
        self._emit_state_changed()

    def set_offset_px(self, offset_px: int, emit_viewport=True):
        clamped = max(0, min(int(offset_px), self.max_offset_px))
        if clamped == self.offset_px:
            if emit_viewport:
                self.scrollbar_state_changed.emit(
                    self.offset_px,
                    self.max_offset_px,
                    self.viewport_width_px,
                )
            return

        self.offset_px = clamped
        self.scrollbar_state_changed.emit(
            self.offset_px,
            self.max_offset_px,
            self.viewport_width_px,
        )
        if emit_viewport:
            self.viewport_changed.emit()

    def scroll_by_pixels(self, delta_px: int):
        self.set_offset_px(self.offset_px + int(delta_px))

    def reset_view(self):
        self.set_offset_px(0)

    def center_on_time(self, time_sec: float):
        center_offset = int(round(float(time_sec) * self.pixels_per_second - self.viewport_width_px / 2))
        self.set_offset_px(center_offset)

    def time_to_view_x(self, time_sec: float) -> float:
        return (float(time_sec) * self.pixels_per_second) - self.offset_px

    def view_x_to_time(self, view_x: float) -> float:
        return (self.offset_px + float(view_x)) / max(self.pixels_per_second, 1)

    def visible_time_range(self) -> tuple[float, float]:
        start_sec = self.offset_px / max(self.pixels_per_second, 1)
        end_sec = min(
            (self.offset_px + self.viewport_width_px) / max(self.pixels_per_second, 1),
            self.duration_sec,
        )
        return start_sec, end_sec

    def visible_content_range_px(self) -> tuple[int, int]:
        return self.offset_px, self.offset_px + self.viewport_width_px

    def _emit_state_changed(self):
        self.scrollbar_state_changed.emit(
            self.offset_px,
            self.max_offset_px,
            self.viewport_width_px,
        )
        self.viewport_changed.emit()
