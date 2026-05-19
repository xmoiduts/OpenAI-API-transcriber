"""
Waveform Drawing Zone widget for the Sentence Aligner tab.

Fixed-zoom horizontal layout at `PIXELS_PER_SECOND`, meant to be hosted inside
a `QScrollArea` so long previews are scrollable horizontally.

Stacked tracks (top to bottom):
  1. Ruler            - major tick every 1s anchored to integer seconds,
                        minor tick every 0.1s; label format m:ss or h:mm:ss
  2. Waveform         - filled amplitude bars
  3. Translation      - rounded rects for translation sentences in view
  4. Original         - rounded rects for original sentences in view
  5. Word             - compact rects for merged word-timestamp entries in view

Sentences belonging to the currently selected aligned row are drawn in the
highlight color; other overlapping neighbours are drawn in gray.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PyQt5.QtWidgets import QWidget, QSizePolicy
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics, QBrush


PIXELS_PER_SECOND = 200

RULER_HEIGHT = 38
WAVEFORM_HEIGHT = 120
TRANSLATION_HEIGHT = 32
ORIGINAL_HEIGHT = 32
WORD_HEIGHT = 28
H_PAD = 50

TOTAL_HEIGHT = (
    RULER_HEIGHT
    + WAVEFORM_HEIGHT
    + TRANSLATION_HEIGHT
    + ORIGINAL_HEIGHT
    + WORD_HEIGHT
)

MAX_CONTENT_WIDTH = 200_000

WAVEFORM_COLOR = QColor("#4A90D9")
WAVEFORM_BG = QColor("#F0F4F8")

SELECTED_BG = QColor("#E8F0FE")
SELECTED_BORDER = QColor("#90B4DE")
SELECTED_TEXT = QColor("#333333")

NEIGHBOUR_BG = QColor("#F2F2F2")
NEIGHBOUR_BORDER = QColor("#CCCCCC")
NEIGHBOUR_TEXT = QColor("#8A8A8A")

TRANSLATION_SELECTED_BG = QColor("#FFF4E0")
TRANSLATION_SELECTED_BORDER = QColor("#D9B48A")
TRANSLATION_SELECTED_TEXT = QColor("#333333")

WORD_BG = QColor("#F6F6F6")
WORD_BORDER = QColor("#C8C8C8")
WORD_TEXT = QColor("#555555")

RULER_TEXT_COLOR = QColor("#666666")
RULER_TICK_COLOR = QColor("#999999")
RULER_MINOR_COLOR = QColor("#BDBDBD")
GRID_COLOR = QColor("#E8E8E8")


@dataclass(frozen=True)
class SentenceEntry:
    start_sec: float
    end_sec: float
    text: str
    row_key: str


@dataclass(frozen=True)
class WordEntry:
    start_sec: float
    end_sec: float
    text: str


class WaveformDrawingZone(QWidget):
    """Fixed-size, horizontally scrollable drawing widget for waveform + tracks."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._amplitudes: np.ndarray | None = None
        self._start_sec: float = 0.0
        self._duration_sec: float = 0.0

        self._orig_entries: list[SentenceEntry] = []
        self._trans_entries: list[SentenceEntry] = []
        self._word_entries: list[WordEntry] = []
        self._selected_row_key: str = ""

        self.setMinimumHeight(TOTAL_HEIGHT)
        self.setFixedHeight(TOTAL_HEIGHT)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setAutoFillBackground(True)

    # ---------------------------------------------------------------- API --
    def set_data(
        self,
        amplitudes: np.ndarray | None,
        start_sec: float,
        duration_sec: float,
        orig_entries: list[SentenceEntry],
        trans_entries: list[SentenceEntry],
        word_entries: list[WordEntry],
        selected_row_key: str,
    ) -> None:
        self._amplitudes = amplitudes
        self._start_sec = float(start_sec)
        self._duration_sec = float(duration_sec)
        self._orig_entries = list(orig_entries)
        self._trans_entries = list(trans_entries)
        self._word_entries = list(word_entries)
        self._selected_row_key = selected_row_key or ""

        self._apply_content_width()
        self.update()

    def clear(self) -> None:
        self._amplitudes = None
        self._orig_entries = []
        self._trans_entries = []
        self._word_entries = []
        self._selected_row_key = ""
        self._apply_content_width()
        self.update()

    def pixel_x_for_time(self, t_sec: float) -> int:
        """Return the widget x-coordinate for an absolute timestamp."""
        rel = t_sec - self._start_sec
        return H_PAD + int(round(rel * PIXELS_PER_SECOND))

    def selected_sentence_midpoint_x(self) -> int | None:
        """x-pixel of the selected sentence's midpoint, or None if no selection."""
        if not self._selected_row_key:
            return None
        for entry in self._orig_entries + self._trans_entries:
            if entry.row_key == self._selected_row_key:
                mid = (entry.start_sec + entry.end_sec) / 2.0
                return self.pixel_x_for_time(mid)
        return None

    def grab_image(self, filepath: str) -> None:
        pixmap = self.grab()
        pixmap.save(filepath, "PNG")

    # ----------------------------------------------------------- Painting --
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        if self._amplitudes is None or self._duration_sec <= 0:
            painter.setPen(QColor("#BBBBBB"))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(
                self.rect(),
                Qt.AlignCenter,
                "Select a subtitle row to preview waveform",
            )
            painter.end()
            return

        draw_w = max(self.width() - 2 * H_PAD, 0)

        y_ruler = 0
        y_wave = RULER_HEIGHT
        y_trans = y_wave + WAVEFORM_HEIGHT
        y_orig = y_trans + TRANSLATION_HEIGHT
        y_word = y_orig + ORIGINAL_HEIGHT

        self._draw_ruler(painter, y_ruler, draw_w)
        self._draw_waveform(painter, y_wave, draw_w)
        self._draw_sentence_track(
            painter, y_trans, TRANSLATION_HEIGHT, self._trans_entries,
            selected_bg=TRANSLATION_SELECTED_BG,
            selected_border=TRANSLATION_SELECTED_BORDER,
            selected_text=TRANSLATION_SELECTED_TEXT,
        )
        self._draw_sentence_track(
            painter, y_orig, ORIGINAL_HEIGHT, self._orig_entries,
            selected_bg=SELECTED_BG,
            selected_border=SELECTED_BORDER,
            selected_text=SELECTED_TEXT,
        )
        self._draw_word_track(painter, y_word, WORD_HEIGHT)

        painter.end()

    # ------------------------------------------------------------ Ruler ---
    def _draw_ruler(self, painter: QPainter, y0: int, draw_w: int) -> None:
        """Top row = integer-second labels; bottom row = tick marks."""
        tick_font = QFont("Consolas", 9)
        painter.setFont(tick_font)
        fm = QFontMetrics(tick_font)
        text_h = fm.height()

        view_start = self._start_sec
        view_end = self._start_sec + self._duration_sec
        tick_line_y_top = y0 + text_h + 2
        tick_line_y_bottom = y0 + RULER_HEIGHT - 1

        painter.setPen(QPen(GRID_COLOR, 1))
        painter.drawLine(H_PAD, tick_line_y_bottom, H_PAD + draw_w, tick_line_y_bottom)

        first_sec = int(math.ceil(view_start - 1e-9))
        last_sec = int(math.floor(view_end + 1e-9))

        for s in range(first_sec, last_sec + 1):
            x = self.pixel_x_for_time(float(s))

            painter.setPen(QPen(RULER_TICK_COLOR, 1))
            painter.drawLine(x, tick_line_y_top, x, tick_line_y_bottom)

            label = _format_ruler_label(s)
            lw = fm.horizontalAdvance(label)
            painter.setPen(RULER_TEXT_COLOR)
            painter.drawText(x - lw // 2, y0 + text_h, label)

            minor_tick_len = 4
            painter.setPen(QPen(RULER_MINOR_COLOR, 1))
            for k in range(1, 10):
                mt = float(s) + 0.1 * k
                if mt > view_end + 1e-9:
                    break
                if mt < view_start - 1e-9:
                    continue
                mx = self.pixel_x_for_time(mt)
                painter.drawLine(
                    mx, tick_line_y_bottom - minor_tick_len, mx, tick_line_y_bottom
                )

    # --------------------------------------------------------- Waveform ---
    def _draw_waveform(self, painter: QPainter, y0: int, draw_w: int) -> None:
        amps = self._amplitudes
        if amps is None:
            return
        n = int(len(amps))
        if n == 0:
            return

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

    # ------------------------------------------------------- Sentence ---
    def _draw_sentence_track(
        self,
        painter: QPainter,
        y0: int,
        height: int,
        entries: list[SentenceEntry],
        selected_bg: QColor,
        selected_border: QColor,
        selected_text: QColor,
    ) -> None:
        if self._duration_sec <= 0:
            return

        view_end = self._start_sec + self._duration_sec

        painter.save()
        label_font = QFont("Microsoft YaHei", 9)

        for entry in entries:
            rel_start = max(entry.start_sec, self._start_sec)
            rel_end = min(entry.end_sec, view_end)
            if rel_end <= rel_start:
                continue

            x1 = self.pixel_x_for_time(rel_start)
            x2 = self.pixel_x_for_time(rel_end)
            rect = QRectF(x1, y0 + 2, max(x2 - x1, 6), height - 4)

            is_selected = entry.row_key == self._selected_row_key
            if is_selected:
                bg = selected_bg
                border = selected_border
                text_color = selected_text
            else:
                bg = NEIGHBOUR_BG
                border = NEIGHBOUR_BORDER
                text_color = NEIGHBOUR_TEXT

            painter.setPen(QPen(border, 1))
            painter.setBrush(QBrush(bg))
            painter.drawRoundedRect(rect, 5, 5)

            if entry.text:
                painter.save()
                painter.setClipRect(rect.adjusted(4, 0, -4, 0))
                painter.setFont(label_font)
                painter.setPen(text_color)
                painter.drawText(
                    rect.adjusted(6, 0, -4, 0),
                    Qt.AlignVCenter | Qt.AlignLeft,
                    entry.text,
                )
                painter.restore()

        painter.restore()

    # --------------------------------------------------------- Word --
    def _draw_word_track(self, painter: QPainter, y0: int, height: int) -> None:
        if self._duration_sec <= 0 or not self._word_entries:
            return

        view_end = self._start_sec + self._duration_sec

        painter.save()
        word_font = QFont("Microsoft YaHei", 8)
        painter.setFont(word_font)

        for entry in self._word_entries:
            rel_start = max(entry.start_sec, self._start_sec)
            rel_end = min(entry.end_sec, view_end)
            if rel_end <= rel_start:
                continue

            x1 = self.pixel_x_for_time(rel_start)
            x2 = self.pixel_x_for_time(rel_end)
            rect = QRectF(x1, y0 + 3, max(x2 - x1, 2), height - 6)

            painter.setPen(QPen(WORD_BORDER, 1))
            painter.setBrush(QBrush(WORD_BG))
            painter.drawRect(rect)

            display_text = _display_word_text(entry.text)
            if display_text and rect.width() >= 6:
                painter.save()
                painter.setClipRect(rect.adjusted(2, 0, -2, 0))
                painter.setPen(WORD_TEXT)
                painter.drawText(
                    rect.adjusted(3, 0, -2, 0),
                    Qt.AlignVCenter | Qt.AlignLeft,
                    display_text,
                )
                painter.restore()

        painter.restore()

    # ------------------------------------------------------- Helpers --
    def _apply_content_width(self) -> None:
        """Resize widget so its width reflects duration * PIXELS_PER_SECOND."""
        if self._duration_sec <= 0:
            parent = self.parentWidget()
            fallback_w = parent.width() if parent is not None else 600
            self.setFixedWidth(max(fallback_w, 400))
            return

        content_w = int(round(self._duration_sec * PIXELS_PER_SECOND)) + 2 * H_PAD
        content_w = max(content_w, 400)
        content_w = min(content_w, MAX_CONTENT_WIDTH)
        self.setFixedWidth(content_w)


# ---------------------------------------------------------- Helpers ------

def _display_word_text(text: str) -> str:
    """Render pure-whitespace payloads as U+2423 (OPEN BOX) so they stay visible."""
    if text != "" and text.strip() == "":
        return "\u2423"
    return text


def _format_ruler_label(seconds: int) -> str:
    """Format integer seconds as m:ss or h:mm:ss."""
    if seconds < 0:
        seconds = 0
    if seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}:{s:02d}"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"
