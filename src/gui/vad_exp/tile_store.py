from collections import OrderedDict

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap
import numpy as np


class AudioStrengthTileStore:
    """Fixed-scale 1D tile cache for audio strength rendering."""

    def __init__(self, tile_width_px=1024, max_tiles=72):
        self.tile_width_px = tile_width_px
        self.max_tiles = max_tiles
        self._cache = OrderedDict()
        self._strength_series = None
        self._revision = 0
        self._status_message = "Waiting for audio parse"

    def clear(self):
        self._cache.clear()
        self._strength_series = None
        self._revision += 1
        self._status_message = "Waiting for audio parse"

    def set_strength_series(self, strength_series: np.ndarray):
        self._strength_series = np.asarray(strength_series, dtype=np.float32)
        self._cache.clear()
        self._revision += 1
        self._status_message = ""

    def set_status_message(self, status_message: str):
        self._status_message = status_message
        self._cache.clear()
        self._revision += 1

    def has_strength_series(self) -> bool:
        return self._strength_series is not None and len(self._strength_series) > 0

    def get_status_message(self) -> str:
        return self._status_message

    def get_tile(
        self,
        method_key: str,
        accent_color: str,
        tile_index: int,
        height: int,
        samples_per_second: int,
        pixels_per_sample: float,
    ) -> QPixmap:
        key = (
            method_key,
            accent_color,
            tile_index,
            height,
            samples_per_second,
            round(pixels_per_sample, 4),
            self._revision,
        )
        pixmap = self._cache.get(key)
        if pixmap is not None:
            self._cache.move_to_end(key)
            return pixmap

        pixmap = self._render_tile(
            method_key=method_key,
            accent_color=accent_color,
            tile_index=tile_index,
            height=height,
            samples_per_second=samples_per_second,
            pixels_per_sample=pixels_per_sample,
        )
        self._cache[key] = pixmap
        self._cache.move_to_end(key)

        while len(self._cache) > self.max_tiles:
            self._cache.popitem(last=False)

        return pixmap

    def _render_tile(
        self,
        method_key: str,
        accent_color: str,
        tile_index: int,
        height: int,
        samples_per_second: int,
        pixels_per_sample: float,
    ) -> QPixmap:
        pixmap = QPixmap(self.tile_width_px, height)
        pixmap.fill(QColor("#F5F8FC"))

        accent = QColor(accent_color)
        bar_pen = QPen(accent.darker(105), 1)
        grid_pen = QPen(QColor("#E6ECF4"), 1)
        baseline_pen = QPen(QColor("#D3DAE6"), 1)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.setPen(grid_pen)
        for x in range(0, self.tile_width_px, 100):
            painter.drawLine(x, 0, x, height)

        painter.setPen(bar_pen)
        baseline_y = height - 10
        amplitude_scale = max(height - 20, 1)
        series = self._strength_series

        if series is not None:
            tile_start_px = tile_index * self.tile_width_px
            series_len = len(series)
            for local_x in range(self.tile_width_px):
                global_x = tile_start_px + local_x
                sample_start = int(global_x / max(pixels_per_sample, 1e-6))
                sample_end = int((global_x + 1) / max(pixels_per_sample, 1e-6))

                if sample_start >= series_len:
                    break

                if sample_end <= sample_start:
                    sample_end = sample_start + 1

                sample_end = min(sample_end, series_len)
                amplitude = float(np.max(series[sample_start:sample_end]))
                bar_height = max(4, int(amplitude * amplitude_scale))
                painter.drawLine(local_x, baseline_y, local_x, baseline_y - bar_height)

        painter.setPen(baseline_pen)
        painter.drawLine(0, baseline_y, self.tile_width_px, baseline_y)
        painter.end()
        return pixmap

    def warm_visible_window(
        self,
        method_key: str,
        accent_color: str,
        offset_px: int,
        viewport_width_px: int,
        height: int,
        samples_per_second: int,
        pixels_per_sample: float,
    ):
        if not self.has_strength_series():
            return
        start_px = max(offset_px - viewport_width_px, 0)
        end_px = offset_px + viewport_width_px * 2
        start_tile = start_px // self.tile_width_px
        end_tile = max(end_px // self.tile_width_px, start_tile)

        for tile_index in range(start_tile, end_tile + 1):
            self.get_tile(
                method_key,
                accent_color,
                tile_index,
                height,
                samples_per_second,
                pixels_per_sample,
            )
