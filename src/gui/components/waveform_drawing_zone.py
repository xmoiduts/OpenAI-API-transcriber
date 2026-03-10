"""
Waveform Drawing Zone widget for the Sentence Aligner tab.

Stacked tracks (top to bottom):
  1. Ruler   - timestamp numbers + tick marks
  2. Waveform - filled amplitude bars
  3. Subtitle - rounded rectangle with original text, time-aligned
  4. Reserved - blank track for future use
"""

import numpy as np
from PyQt5.QtWidgets import QWidget, QSizePolicy
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics, QBrush


# Track layout constants (heights in pixels)
RULER_HEIGHT = 38
WAVEFORM_HEIGHT = 120
SUBTITLE_HEIGHT = 36
RESERVED_HEIGHT = 30
H_PAD = 50  # left/right padding for the drawing area (time labels live here)

WAVEFORM_COLOR = QColor("#4A90D9")
WAVEFORM_BG = QColor("#F0F4F8")
SUBTITLE_BG = QColor("#E8F0FE")
SUBTITLE_BORDER = QColor("#90B4DE")
RULER_TEXT_COLOR = QColor("#666666")
RULER_TICK_COLOR = QColor("#999999")
GRID_COLOR = QColor("#E8E8E8")
RESERVED_BG = QColor("#FAFAFA")
RESERVED_BORDER = QColor("#E0E0E0")


class WaveformDrawingZone(QWidget):
    """Custom-painted widget showing waveform, subtitle track, and time ruler."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._amplitudes: np.ndarray | None = None
        self._start_sec: float = 0.0
        self._duration_sec: float = 0.0
        self._subtitle_text: str = ""
        self._sub_start_sec: float = 0.0
        self._sub_end_sec: float = 0.0

        self.setMinimumHeight(
            RULER_HEIGHT + WAVEFORM_HEIGHT + SUBTITLE_HEIGHT + RESERVED_HEIGHT
        )
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # ---------------------------------------------------------------- API --
    def set_data(
        self,
        amplitudes: np.ndarray,
        start_sec: float,
        duration_sec: float,
        subtitle_text: str = "",
        sub_start_sec: float = 0.0,
        sub_end_sec: float = 0.0,
    ):
        """Load new waveform + subtitle data and repaint."""
        self._amplitudes = amplitudes
        self._start_sec = start_sec
        self._duration_sec = duration_sec
        self._subtitle_text = subtitle_text
        self._sub_start_sec = sub_start_sec
        self._sub_end_sec = sub_end_sec
        self.update()

    def clear(self):
        self._amplitudes = None
        self._subtitle_text = ""
        self.update()

    def grab_image(self, filepath: str):
        """Rasterize the widget to a PNG file for AI consumption."""
        pixmap = self.grab()
        pixmap.save(filepath, "PNG")

    # ----------------------------------------------------------- Painting --
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        draw_w = w - 2 * H_PAD

        y_ruler = 0
        y_wave = RULER_HEIGHT
        y_sub = RULER_HEIGHT + WAVEFORM_HEIGHT
        y_reserved = y_sub + SUBTITLE_HEIGHT

        # Background
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        if self._amplitudes is None or self._duration_sec <= 0:
            painter.setPen(QColor("#BBBBBB"))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(self.rect(), Qt.AlignCenter, "Select a subtitle row to preview waveform")
            painter.end()
            return

        self._draw_ruler(painter, y_ruler, draw_w)
        self._draw_waveform(painter, y_wave, draw_w)
        self._draw_subtitle_track(painter, y_sub, draw_w)
        self._draw_reserved_track(painter, y_reserved, draw_w, self.height() - y_reserved)

        painter.end()

    # ------------------------------------------------------------ Ruler ---
    def _draw_ruler(self, painter: QPainter, y0: int, draw_w: int):
        """Two rows: top = time numbers, bottom = tick marks."""
        tick_font = QFont("Consolas", 9)
        painter.setFont(tick_font)
        fm = QFontMetrics(tick_font)
        text_h = fm.height()

        # Choose a nice tick interval based on duration
        tick_interval = _choose_tick_interval(self._duration_sec)
        minor_count = 5  # minor ticks between major ticks

        t = 0.0
        major_i = 0
        while t <= self._duration_sec + 1e-9:
            x = H_PAD + int((t / self._duration_sec) * draw_w)

            # Major tick + label
            painter.setPen(QPen(RULER_TICK_COLOR, 1))
            painter.drawLine(x, y0 + text_h + 2, x, y0 + RULER_HEIGHT - 1)

            label = _format_ruler_time(self._start_sec + t)
            lw = fm.horizontalAdvance(label)
            painter.setPen(RULER_TEXT_COLOR)
            painter.drawText(x - lw // 2, y0 + text_h, label)

            # Minor ticks
            if t + tick_interval <= self._duration_sec + 1e-9:
                minor_step = tick_interval / minor_count
                for mi in range(1, minor_count):
                    mt = t + mi * minor_step
                    if mt > self._duration_sec:
                        break
                    mx = H_PAD + int((mt / self._duration_sec) * draw_w)
                    tick_len = 4
                    painter.setPen(QPen(RULER_TICK_COLOR, 1))
                    painter.drawLine(mx, y0 + RULER_HEIGHT - 1 - tick_len, mx, y0 + RULER_HEIGHT - 1)

            t += tick_interval
            major_i += 1

        # Bottom line of ruler
        painter.setPen(QPen(GRID_COLOR, 1))
        painter.drawLine(H_PAD, y0 + RULER_HEIGHT - 1, H_PAD + draw_w, y0 + RULER_HEIGHT - 1)

    # --------------------------------------------------------- Waveform ---
    def _draw_waveform(self, painter: QPainter, y0: int, draw_w: int):
        """Filled amplitude bars (area-under-curve style)."""
        amps = self._amplitudes
        n = len(amps)
        if n == 0:
            return

        # Background
        painter.fillRect(QRectF(H_PAD, y0, draw_w, WAVEFORM_HEIGHT), WAVEFORM_BG)

        bar_w = max(draw_w / n, 1.0)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(WAVEFORM_COLOR))

        for i in range(n):
            amp = float(amps[i])
            bar_h = max(amp * (WAVEFORM_HEIGHT - 4), 1)
            x = H_PAD + (i / n) * draw_w
            y = y0 + WAVEFORM_HEIGHT - 2 - bar_h
            painter.drawRect(QRectF(x, y, bar_w, bar_h))

    # ------------------------------------------------------- Subtitle ---
    def _draw_subtitle_track(self, painter: QPainter, y0: int, draw_w: int):
        """Rounded rectangle with original text, time-aligned to waveform."""
        if not self._subtitle_text or self._duration_sec <= 0:
            return

        rel_start = max(self._sub_start_sec - self._start_sec, 0)
        rel_end = min(self._sub_end_sec - self._start_sec, self._duration_sec)
        if rel_end <= rel_start:
            return

        x1 = H_PAD + int((rel_start / self._duration_sec) * draw_w)
        x2 = H_PAD + int((rel_end / self._duration_sec) * draw_w)
        rect_w = max(x2 - x1, 20)

        rect = QRectF(x1, y0 + 2, rect_w, SUBTITLE_HEIGHT - 4)
        painter.setPen(QPen(SUBTITLE_BORDER, 1))
        painter.setBrush(QBrush(SUBTITLE_BG))
        painter.drawRoundedRect(rect, 6, 6)

        # Text inside, clipped to the rect
        painter.save()
        painter.setClipRect(rect.adjusted(4, 0, -4, 0))
        painter.setPen(QColor("#333333"))
        painter.setFont(QFont("Microsoft YaHei", 9))
        painter.drawText(rect.adjusted(6, 0, -4, 0), Qt.AlignVCenter | Qt.AlignLeft, self._subtitle_text)
        painter.restore()

    # ------------------------------------------------------ Reserved ---
    def _draw_reserved_track(self, painter: QPainter, y0: int, draw_w: int, height: int):
        """Blank reserved track with subtle border."""
        rect = QRectF(H_PAD, y0 + 2, draw_w, max(height - 4, RESERVED_HEIGHT - 4))
        painter.setPen(QPen(RESERVED_BORDER, 1, Qt.DashLine))
        painter.setBrush(QBrush(RESERVED_BG))
        painter.drawRoundedRect(rect, 4, 4)


# ---------------------------------------------------------- Helpers ------

def _choose_tick_interval(duration: float) -> float:
    """Pick a human-friendly major tick interval for the given duration."""
    candidates = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
    for c in candidates:
        if duration / c <= 15:
            return c
    return 60.0


def _format_ruler_time(seconds: float) -> str:
    """Format seconds for ruler labels: '1.20s' for short, '1:02.3' for long."""
    if seconds < 60:
        return f"{seconds:.2f}s"
    m = int(seconds) // 60
    s = seconds - m * 60
    return f"{m}:{s:05.2f}"
