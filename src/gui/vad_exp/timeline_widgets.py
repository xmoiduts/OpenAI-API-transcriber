import bisect
import math
from dataclasses import dataclass

from PyQt5.QtCore import Qt, QRectF, QEvent, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter, QPen
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QButtonGroup,
    QGestureEvent,
    QPinchGesture,
    QPushButton,
    QScrollBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from src.vad.models import AudioStrengthPatch, VadTimeRange
from .tile_store import AudioStrengthTileStore
from .timeline_controller import TimelineController


RULER_HEIGHT = 36
AUDIO_TRACK_HEIGHT = 108
VAD_TRACK_HEIGHT = 38
METHOD_TRACK_HEIGHT = AUDIO_TRACK_HEIGHT + VAD_TRACK_HEIGHT
CONTROL_PANEL_WIDTH = 220
PROGRESS_BAR_HEIGHT = 8
PROGRESS_BAR_MARGIN = 6
SLICE_LENGTH_PRESETS = ("~10min", "<3min", "<1min", "<30s")
SLICE_TOOL_DEFAULT_NOTE = "Hover a Slice Tool control for guidance.\n "


@dataclass(frozen=True)
class VadInterval:
    start_sec: float
    end_sec: float
    label: str


@dataclass(frozen=True)
class VadMethodSpec:
    method_key: str
    title: str
    accent_color: str
    description: str


class NoteButton(QPushButton):
    """Button that writes a short guide into its owning notebar on hover."""

    def __init__(self, text: str, note: str, note_label: QLabel, parent=None):
        super().__init__(text, parent)
        self._note = note
        self._note_label = note_label

    def enterEvent(self, event):
        self._note_label.setText(self._note)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._note_label.setText(SLICE_TOOL_DEFAULT_NOTE)
        super().leaveEvent(event)


class PannableTrackWidget(QWidget):
    """Base class for widgets that pan the shared timeline by dragging."""

    def __init__(self, controller: TimelineController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self._drag_last_global_x = None
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_AcceptTouchEvents, True)
        self.grabGesture(Qt.PinchGesture)
        self.controller.viewport_changed.connect(self.update)

    def event(self, event):
        if event.type() == QEvent.Gesture:
            return self._handle_gesture_event(event)
        return super().event(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_last_global_x = event.globalX()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_last_global_x is not None:
            delta_x = event.globalX() - self._drag_last_global_x
            self._drag_last_global_x = event.globalX()
            self.controller.scroll_by_pixels(-delta_x)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drag_last_global_x is not None:
            self._drag_last_global_x = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event):
        if self._drag_last_global_x is None:
            self.unsetCursor()
        super().leaveEvent(event)

    def wheelEvent(self, event):
        modifiers = event.modifiers()
        pixel_delta = event.pixelDelta()
        angle_delta = event.angleDelta()

        # Touchpad scrolling usually reports pixelDelta; we ignore vertical swipes
        # and pan horizontally on left/right swipes.
        if not pixel_delta.isNull():
            if modifiers & Qt.AltModifier:
                event.accept()
                return

            if pixel_delta.x() != 0:
                self.controller.scroll_by_pixels(-pixel_delta.x() * 0.5)
            event.accept()
            return

        if modifiers & Qt.AltModifier:
            delta = angle_delta.y() or angle_delta.x()
            if delta != 0:
                factor = 1.20 if delta > 0 else 1 / 1.20
                self.controller.zoom_by_factor(factor, event.pos().x())
            event.accept()
            return

        delta = angle_delta.y() or angle_delta.x()
        if delta != 0:
            # Wheel down => look further into the future (scroll right).
            self.controller.scroll_by_pixels(int((-delta / 120.0) * 180))
            event.accept()
            return

        super().wheelEvent(event)

    def _handle_gesture_event(self, event):
        if not isinstance(event, QGestureEvent):
            return False

        pinch = event.gesture(Qt.PinchGesture)
        if pinch is None:
            return False

        if isinstance(pinch, QPinchGesture):
            last_factor = pinch.lastScaleFactor() or 1.0
            scale_factor = pinch.scaleFactor() or 1.0
            delta_factor = scale_factor / last_factor if last_factor else scale_factor
            center_x = max(0.0, min(float(pinch.centerPoint().x()), float(self.width())))
            self.controller.zoom_by_factor(delta_factor, center_x)
            event.accept()
            return True

        return False


class TimelineRulerWidget(PannableTrackWidget):
    """Shared top ruler rendered from the current viewport only."""

    def __init__(self, controller: TimelineController, parent=None):
        super().__init__(controller, parent)
        self.setFixedHeight(RULER_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.controller.set_viewport_width(self.width())

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        start_sec, end_sec = self.controller.visible_time_range()
        tick_interval = _choose_tick_interval(max(end_sec - start_sec, 0.1))
        first_tick = int(start_sec / tick_interval) * tick_interval
        if first_tick > start_sec:
            first_tick -= tick_interval

        painter.setFont(QFont("Consolas", 9))
        painter.setPen(QPen(QColor("#9A9A9A"), 1))

        tick = first_tick
        while tick <= end_sec + tick_interval:
            x = self.controller.time_to_view_x(tick)
            if -40 <= x <= self.width() + 40:
                painter.drawLine(int(x), 14, int(x), RULER_HEIGHT)
                painter.setPen(QColor("#666666"))
                painter.drawText(int(x) + 4, 12, _format_time_label(tick))
                painter.setPen(QPen(QColor("#9A9A9A"), 1))
            tick += tick_interval

        painter.setPen(QPen(QColor("#DADADA"), 1))
        painter.drawLine(0, RULER_HEIGHT - 1, self.width(), RULER_HEIGHT - 1)
        painter.end()


class MethodTimelineTrackWidget(PannableTrackWidget):
    """Shared-viewport track: tiled audio strength plus overlay VAD blocks."""

    cut_created = pyqtSignal(int)
    cut_deleted = pyqtSignal(int)

    def __init__(
        self,
        controller: TimelineController,
        tile_store: AudioStrengthTileStore,
        method_spec: VadMethodSpec,
        vad_intervals: list[VadInterval],
        parent=None,
    ):
        super().__init__(controller, parent)
        self.tile_store = tile_store
        self.method_spec = method_spec
        self.vad_intervals = vad_intervals
        self.setFixedHeight(METHOD_TRACK_HEIGHT)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.blade_mode_active = False
        self.confirmed_cuts: list[int] = []
        self._hover_time_sec: float | None = None
        self._snapped_sec: int | None = None
        self._mouse_inside = False
        self.processed_ranges: list[VadTimeRange] = []
        self.active_ranges: list[VadTimeRange] = []

    def set_vad_intervals(self, vad_intervals: list[VadInterval]):
        self.vad_intervals = vad_intervals
        self.update()

    def set_processing_state(
        self,
        processed_ranges: list[VadTimeRange],
        active_ranges: list[VadTimeRange],
    ):
        self.processed_ranges = list(processed_ranges)
        self.active_ranges = list(active_ranges)
        self.update()

    def set_blade_mode(self, active: bool):
        self.blade_mode_active = active
        if not active:
            self._hover_time_sec = None
            self._snapped_sec = None
        self.update()

    def get_slices(self, duration: float) -> list[tuple[int, int]]:
        """Convert confirmed cut points into (start, duration) pairs."""
        cuts = sorted(self.confirmed_cuts)
        end = math.ceil(duration)
        boundaries = [0] + cuts + [end]
        slices = []
        for i in range(len(boundaries) - 1):
            s = boundaries[i]
            d = boundaries[i + 1] - s
            if d > 0:
                slices.append((s, d))
        return slices

    # -- Mouse overrides for blade mode ---------------------------------

    def enterEvent(self, event):
        self._mouse_inside = True
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._mouse_inside = False
        if self.blade_mode_active:
            self._hover_time_sec = None
            self._snapped_sec = None
            self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self.blade_mode_active and event.button() == Qt.LeftButton:
            time_sec = self.controller.view_x_to_time(event.pos().x())
            snapped = max(0, round(time_sec))
            if event.modifiers() & Qt.ShiftModifier:
                if snapped in self.confirmed_cuts:
                    self.confirmed_cuts.remove(snapped)
                    self.cut_deleted.emit(snapped)
            else:
                if snapped not in self.confirmed_cuts:
                    bisect.insort(self.confirmed_cuts, snapped)
                    self.cut_created.emit(snapped)
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.blade_mode_active and self._drag_last_global_x is None:
            time_sec = self.controller.view_x_to_time(event.pos().x())
            self._hover_time_sec = time_sec
            self._snapped_sec = max(0, round(time_sec))
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    # -- Paint -----------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))

        audio_rect = QRectF(0, 0, self.width(), AUDIO_TRACK_HEIGHT)
        vad_rect = QRectF(0, AUDIO_TRACK_HEIGHT, self.width(), VAD_TRACK_HEIGHT)

        self._draw_audio_tiles(painter, audio_rect)
        self._draw_vad_overlay(painter, vad_rect)

        painter.setPen(QPen(QColor("#DADADA"), 1))
        painter.drawLine(0, AUDIO_TRACK_HEIGHT - 1, self.width(), AUDIO_TRACK_HEIGHT - 1)
        painter.drawLine(0, METHOD_TRACK_HEIGHT - 1, self.width(), METHOD_TRACK_HEIGHT - 1)

        self._draw_blade_overlay(painter)
        painter.end()

    def _draw_blade_overlay(self, painter: QPainter):
        accent = QColor(self.method_spec.accent_color)

        for cut_sec in self.confirmed_cuts:
            x = self.controller.time_to_view_x(float(cut_sec))
            if -2 <= x <= self.width() + 2:
                painter.setPen(QPen(accent, 2))
                painter.drawLine(int(x), 0, int(x), METHOD_TRACK_HEIGHT)

        if not self.blade_mode_active:
            return

        if not self._mouse_inside or self._hover_time_sec is None:
            return

        hover_x = self.controller.time_to_view_x(self._hover_time_sec)
        painter.setPen(QPen(QColor("#888888"), 1, Qt.DashLine))
        painter.drawLine(int(hover_x), 0, int(hover_x), METHOD_TRACK_HEIGHT)

        if self._snapped_sec is not None and self._snapped_sec not in self.confirmed_cuts:
            snap_x = self.controller.time_to_view_x(float(self._snapped_sec))
            dimmed = QColor(accent)
            dimmed.setAlpha(100)
            painter.setPen(QPen(dimmed, 2))
            painter.drawLine(int(snap_x), 0, int(snap_x), METHOD_TRACK_HEIGHT)

        if self._snapped_sec is not None:
            prev_boundary = 0
            for cut in self.confirmed_cuts:
                if cut < self._snapped_sec:
                    prev_boundary = cut
                else:
                    break
            upcoming_sec = self._snapped_sec - prev_boundary
            mins = upcoming_sec // 60
            secs = upcoming_sec % 60
            text = f"upcoming: {mins} min {secs:02d} s"

            painter.setFont(QFont("Consolas", 10))
            fm = painter.fontMetrics()
            text_w = fm.horizontalAdvance(text) + 16
            text_h = fm.height() + 8
            bg_rect = QRectF(8, 8, text_w, text_h)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(60, 60, 60, 200))
            painter.drawRoundedRect(bg_rect, 4, 4)
            painter.setPen(QColor("#FFFFFF"))
            painter.setBrush(Qt.NoBrush)
            painter.drawText(bg_rect, Qt.AlignCenter, text)

    def _draw_audio_tiles(self, painter: QPainter, audio_rect: QRectF):
        painter.save()
        painter.setClipRect(audio_rect)
        painter.fillRect(audio_rect, QColor("#F5F8FC"))

        self._draw_progress_strip(
            painter,
            QRectF(
                audio_rect.left(),
                audio_rect.top(),
                audio_rect.width(),
                PROGRESS_BAR_HEIGHT,
            ),
        )

        if not self.tile_store.has_strength_series():
            painter.setPen(QColor("#7D8899"))
            painter.setFont(QFont("Segoe UI", 10))
            painter.drawText(
                audio_rect,
                Qt.AlignCenter,
                self.tile_store.get_status_message() or "Audio strength unavailable",
            )
            painter.restore()
            return

        self._draw_active_range_overlay(
            painter,
            audio_rect.adjusted(0, PROGRESS_BAR_HEIGHT + PROGRESS_BAR_MARGIN, 0, 0),
            fill_color=QColor(74, 144, 217, 36),
        )

        tile_width = self.tile_store.tile_width_px
        offset_px = self.controller.offset_px
        viewport_width_px = self.controller.viewport_width_px

        start_tile = max(offset_px // tile_width, 0)
        end_tile = max((offset_px + viewport_width_px) // tile_width, start_tile)

        self.tile_store.warm_visible_window(
            method_key=self.method_spec.method_key,
            accent_color=self.method_spec.accent_color,
            offset_px=offset_px,
            viewport_width_px=viewport_width_px,
            height=int(audio_rect.height()),
            samples_per_second=self.controller.samples_per_second,
            pixels_per_sample=self.controller.pixels_per_sample,
        )

        for tile_index in range(start_tile, end_tile + 1):
            pixmap = self.tile_store.get_tile(
                method_key=self.method_spec.method_key,
                accent_color=self.method_spec.accent_color,
                tile_index=tile_index,
                height=int(audio_rect.height()),
                samples_per_second=self.controller.samples_per_second,
                pixels_per_sample=self.controller.pixels_per_sample,
            )
            draw_x = tile_index * tile_width - offset_px
            painter.drawPixmap(int(draw_x), int(audio_rect.top()), pixmap)

        if self.tile_store.get_status_message():
            painter.setPen(QColor("#6A788D"))
            painter.setFont(QFont("Segoe UI", 8))
            painter.drawText(
                QRectF(12, 46, min(self.width() - 24, 520), 16),
                Qt.AlignLeft | Qt.AlignVCenter,
                self.tile_store.get_status_message(),
            )

        painter.setPen(QColor("#44546A"))
        painter.setFont(QFont("Segoe UI", 10))
        painter.drawText(
            QRectF(12, 16, min(self.width() - 24, 320), 20),
            Qt.AlignLeft | Qt.AlignVCenter,
            f"{self.method_spec.title} strength",
        )
        painter.setPen(QColor("#96A2B5"))
        painter.setFont(QFont("Segoe UI", 8))
        painter.drawText(
            QRectF(12, 34, min(self.width() - 24, 460), 16),
            Qt.AlignLeft | Qt.AlignVCenter,
            f"Actual audio strength tiles (50 samples/sec, zoom {self.controller.pixels_per_sample:.2f} px/sample)",
        )
        painter.restore()

    def _draw_vad_overlay(self, painter: QPainter, vad_rect: QRectF):
        painter.save()
        painter.setClipRect(vad_rect)
        painter.fillRect(vad_rect, QColor("#ECEFF3"))

        processed_fill = QColor("#FAFAFA")
        self._draw_time_ranges(painter, vad_rect, self.processed_ranges, processed_fill)
        self._draw_time_ranges(
            painter,
            vad_rect,
            self.active_ranges,
            QColor(74, 144, 217, 52),
        )

        start_sec, end_sec = self.controller.visible_time_range()
        accent = QColor(self.method_spec.accent_color)

        border_pen = QPen(QColor("#C5CBD5"), 1, Qt.DashLine)
        painter.setPen(border_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(vad_rect.adjusted(8, 6, -8, -6), 4, 4)

        for interval in self.vad_intervals:
            if interval.end_sec < start_sec or interval.start_sec > end_sec:
                continue

            x1 = self.controller.time_to_view_x(interval.start_sec)
            x2 = self.controller.time_to_view_x(interval.end_sec)
            rect_left = max(x1, 8)
            rect_right = min(x2, self.width() - 8)
            rect_width = max(rect_right - rect_left, 6)
            rect = QRectF(rect_left, vad_rect.top() + 8, rect_width, vad_rect.height() - 16)

            fill = QColor(accent)
            fill.setAlpha(70)
            painter.setPen(QPen(accent.darker(110), 1))
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, 4, 4)

            if rect.width() > 48:
                painter.setPen(QColor("#334155"))
                painter.setFont(QFont("Segoe UI", 8))
                painter.drawText(rect.adjusted(6, 0, -4, 0), Qt.AlignVCenter | Qt.AlignLeft, interval.label)

        painter.setPen(QColor("#7D8899"))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(
            QRectF(12, vad_rect.top(), min(self.width() - 24, 260), vad_rect.height()),
            Qt.AlignLeft | Qt.AlignVCenter,
            "VAD overlay track",
        )
        painter.restore()

    def _draw_progress_strip(self, painter: QPainter, strip_rect: QRectF):
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#D5DADF"))
        painter.drawRect(strip_rect)
        self._draw_time_ranges(painter, strip_rect, self.processed_ranges, QColor("#58B36A"))
        self._draw_time_ranges(painter, strip_rect, self.active_ranges, QColor("#4A90D9"))
        painter.setPen(QPen(QColor("#C2C8D0"), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(strip_rect.adjusted(0, 0, -1, -1))
        painter.restore()

    def _draw_active_range_overlay(self, painter: QPainter, rect: QRectF, fill_color: QColor):
        if rect.height() <= 0:
            return
        self._draw_time_ranges(painter, rect, self.active_ranges, fill_color)

    def _draw_time_ranges(
        self,
        painter: QPainter,
        target_rect: QRectF,
        time_ranges: list[VadTimeRange],
        fill_color: QColor,
    ):
        if not time_ranges:
            return
        painter.save()
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill_color)
        for time_range in time_ranges:
            x1 = self.controller.time_to_view_x(time_range.start_sec)
            x2 = self.controller.time_to_view_x(time_range.end_sec)
            rect_left = max(x1, target_rect.left())
            rect_right = min(x2, target_rect.right())
            if rect_right <= rect_left:
                continue
            painter.drawRect(QRectF(rect_left, target_rect.top(), rect_right - rect_left, target_rect.height()))
        painter.restore()


class MethodControlPanel(QFrame):
    """Left-side control block for one VAD method and its Slice Tool."""

    manual_toggled = pyqtSignal(bool)
    auto_toggled = pyqtSignal(bool)
    send_clicked = pyqtSignal()
    slice_length_changed = pyqtSignal(str)

    def __init__(self, method_spec: VadMethodSpec, supports_auto_slice: bool = True, parent=None):
        super().__init__(parent)
        self.method_spec = method_spec
        self.supports_auto_slice = supports_auto_slice
        self.active_slice_length = "~10min"
        self.setObjectName("vadControlPanel")
        self.setMinimumWidth(CONTROL_PANEL_WIDTH)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title_label = QLabel(method_spec.title)
        title_label.setObjectName("vadMethodTitle")
        layout.addWidget(title_label)

        description = QLabel(method_spec.description)
        description.setWordWrap(True)
        layout.addWidget(description)

        self.slice_tool_button = QPushButton("Slice Tool")
        self.slice_tool_button.setCheckable(True)
        self.slice_tool_button.setMinimumHeight(30)
        self.slice_tool_button.clicked.connect(self._set_tool_panel_visible)
        layout.addWidget(self.slice_tool_button)

        self.tool_panel = QFrame()
        self.tool_panel.setObjectName("sliceToolPanel")
        panel_layout = QVBoxLayout(self.tool_panel)
        panel_layout.setContentsMargins(8, 8, 8, 8)
        panel_layout.setSpacing(6)

        panel_title = QLabel(f"Slice Tool: {method_spec.title}")
        panel_title.setWordWrap(True)
        panel_layout.addWidget(panel_title)

        self.note_label = QLabel(SLICE_TOOL_DEFAULT_NOTE)
        self.note_label.setObjectName("sliceToolNote")
        self.note_label.setWordWrap(True)
        self.note_label.setMinimumHeight(self.note_label.fontMetrics().lineSpacing() * 2 + 8)
        panel_layout.addWidget(self.note_label)

        panel_layout.addWidget(QLabel("Slice length:"))
        length_row = QHBoxLayout()
        length_row.setSpacing(4)
        self.length_group = QButtonGroup(self)
        self.length_group.setExclusive(True)
        self.length_buttons = {}
        for preset in SLICE_LENGTH_PRESETS:
            button = NoteButton(
                preset,
                "Propose the length of each slice. ~ is soft target; < is hard maximum.",
                self.note_label,
            )
            button.setCheckable(True)
            button.setMinimumWidth(48)
            button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            button.setStyleSheet(_slice_tool_button_stylesheet())
            button.clicked.connect(lambda checked, value=preset: self._on_slice_length_clicked(value))
            self.length_group.addButton(button)
            self.length_buttons[preset] = button
            length_row.addWidget(button)
        self.length_buttons[self.active_slice_length].setChecked(True)
        panel_layout.addLayout(length_row)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(6)

        self.manual_button = NoteButton(
            "Manual Slice",
            "Click the timeline to add a cut; Shift+click an existing cut to remove it.",
            self.note_label,
        )
        self.manual_button.setCheckable(True)
        self.manual_button.setMinimumHeight(28)
        self.manual_button.setStyleSheet(_slice_tool_button_stylesheet())
        self.manual_button.clicked.connect(self._on_manual_toggled)
        mode_row.addWidget(self.manual_button)

        self.auto_button = NoteButton(
            "Auto Slice",
            "Start auto slicing from the latest cut point using VAD silence gaps. Click again to stop.",
            self.note_label,
        )
        self.auto_button.setCheckable(True)
        self.auto_button.setMinimumHeight(28)
        self.auto_button.setEnabled(self.supports_auto_slice)
        self.auto_button.setStyleSheet(_slice_tool_button_stylesheet())
        self.auto_button.clicked.connect(self._on_auto_toggled)
        mode_row.addWidget(self.auto_button)
        panel_layout.addLayout(mode_row)

        self.send_button = NoteButton(
            "Send slices to transcribe tab",
            "Approve these cut points and send the resulting slices to the Transcription tab.",
            self.note_label,
        )
        self.send_button.setMinimumHeight(30)
        self.send_button.setStyleSheet(_slice_tool_button_stylesheet())
        self.send_button.clicked.connect(self.send_clicked.emit)
        panel_layout.addWidget(self.send_button)

        self.tool_panel.hide()
        self.tool_panel.setMinimumWidth(320)
        self.tool_panel.setStyleSheet(_slice_tool_panel_stylesheet())

        if not self.supports_auto_slice:
            self.auto_button.setToolTip("Auto slicing is disabled until this VAD method has a real engine.")

        layout.addStretch()

    def _set_tool_panel_visible(self, visible: bool):
        if visible:
            self._show_tool_panel()
        else:
            self.tool_panel.hide()

    def _show_tool_panel(self):
        container = self._floating_container()
        if container is not None and self.tool_panel.parent() is not container:
            self.tool_panel.setParent(container)
        self.tool_panel.adjustSize()
        global_pos = self.slice_tool_button.mapToGlobal(self.slice_tool_button.rect().bottomLeft())
        if container is not None:
            local_pos = container.mapFromGlobal(global_pos)
            max_x = max(container.width() - self.tool_panel.width() - 8, 8)
            local_pos.setX(max(8, min(local_pos.x(), max_x)))
            local_pos.setY(max(8, min(local_pos.y(), max(container.height() - self.tool_panel.height() - 8, 8))))
            self.tool_panel.move(local_pos)
        self.tool_panel.show()
        self.tool_panel.raise_()

    def hide_tool_panel(self):
        self.tool_panel.hide()
        self.slice_tool_button.setChecked(False)

    def _floating_container(self):
        parent = self.parentWidget()
        while parent is not None:
            if parent.__class__.__name__ == "VADExpTab":
                return parent
            parent = parent.parentWidget()
        return self.parentWidget()

    def _on_slice_length_clicked(self, preset: str):
        if preset == self.active_slice_length:
            self.length_buttons[preset].setChecked(True)
            return
        self.active_slice_length = preset
        self.slice_length_changed.emit(preset)

    def set_slice_length_preset(self, preset: str):
        if preset not in self.length_buttons:
            return
        self.active_slice_length = preset
        self.length_buttons[preset].setChecked(True)

    def _on_manual_toggled(self, checked: bool):
        self._apply_manual_state(checked)
        self.manual_toggled.emit(checked)

    def _on_auto_toggled(self, checked: bool):
        if not self.supports_auto_slice:
            self.auto_button.setChecked(False)
            return
        self._apply_auto_state(checked)
        self.auto_toggled.emit(checked)

    def _apply_manual_state(self, active: bool):
        self.auto_button.setEnabled(not active and self.supports_auto_slice)
        self.send_button.setEnabled(not active)
        for button in self.length_buttons.values():
            button.setEnabled(not active)

    def _apply_auto_state(self, active: bool):
        self.manual_button.setEnabled(not active)
        self.send_button.setEnabled(not active)
        for button in self.length_buttons.values():
            button.setEnabled(not active)

    def set_manual_checked(self, checked: bool):
        self.manual_button.blockSignals(True)
        self.manual_button.setChecked(checked)
        self.manual_button.blockSignals(False)
        self._apply_manual_state(checked)

    def set_auto_checked(self, checked: bool):
        self.auto_button.blockSignals(True)
        self.auto_button.setChecked(checked)
        self.auto_button.blockSignals(False)
        self._apply_auto_state(checked)

    def set_idle_enabled(self, enabled: bool):
        self.slice_tool_button.setEnabled(enabled)
        if not self.manual_button.isChecked() and not self.auto_button.isChecked():
            self.manual_button.setEnabled(enabled)
            self.auto_button.setEnabled(enabled and self.supports_auto_slice)
            self.send_button.setEnabled(enabled)
            for button in self.length_buttons.values():
                button.setEnabled(enabled)


class VadMethodRow(QFrame):
    """Composite row with fixed control block and shared-viewport track."""

    send_slices = pyqtSignal(list)
    manual_cut_created = pyqtSignal(object, int)
    auto_toggled = pyqtSignal(object, bool)
    slice_length_changed = pyqtSignal(object, str)

    def __init__(
        self,
        controller: TimelineController,
        tile_store: AudioStrengthTileStore,
        method_spec: VadMethodSpec,
        vad_intervals: list[VadInterval],
        parent=None,
    ):
        super().__init__(parent)
        self.method_spec = method_spec
        self.setObjectName("vadMethodPanel")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.control_panel = MethodControlPanel(
            method_spec,
            supports_auto_slice=method_spec.method_key == "silero",
        )
        self.track_widget = MethodTimelineTrackWidget(
            controller=controller,
            tile_store=tile_store,
            method_spec=method_spec,
            vad_intervals=vad_intervals,
        )

        layout.addWidget(self.control_panel)
        layout.addWidget(self.track_widget, stretch=1)

        self.control_panel.manual_toggled.connect(self._on_manual_toggled)
        self.control_panel.auto_toggled.connect(self._on_auto_toggled)
        self.control_panel.slice_length_changed.connect(self._on_slice_length_changed)
        self.control_panel.send_clicked.connect(self._on_send_slices)
        self.track_widget.cut_created.connect(self._on_cut_created)

    def _on_send_slices(self):
        slices = self.track_widget.get_slices(
            self.track_widget.controller.duration_sec,
        )
        if self.track_widget.blade_mode_active:
            self.control_panel.set_manual_checked(False)
            self.track_widget.set_blade_mode(False)
        self.send_slices.emit(slices)

    def latest_cut_sec(self) -> float:
        if not self.track_widget.confirmed_cuts:
            return 0.0
        return float(max(self.track_widget.confirmed_cuts))

    def add_confirmed_cut(self, cut_sec: float) -> int:
        snapped = max(0, round(float(cut_sec)))
        if snapped not in self.track_widget.confirmed_cuts:
            bisect.insort(self.track_widget.confirmed_cuts, snapped)
            self.track_widget.update()
        return snapped

    def set_auto_running(self, running: bool):
        self.control_panel.set_auto_checked(running)

    def set_slice_length_preset(self, preset: str):
        self.control_panel.set_slice_length_preset(preset)

    def hide_slice_tool_panel(self):
        self.control_panel.hide_tool_panel()

    def _on_manual_toggled(self, checked: bool):
        self.track_widget.set_blade_mode(checked)

    def _on_auto_toggled(self, checked: bool):
        self.auto_toggled.emit(self, checked)

    def _on_slice_length_changed(self, preset: str):
        self.slice_length_changed.emit(self, preset)

    def _on_cut_created(self, cut_sec: int):
        self.manual_cut_created.emit(self, cut_sec)


class VadTimelinePanel(QWidget):
    """Shared ruler, method rows, and one bottom scrollbar."""

    def __init__(self, method_specs: list[VadMethodSpec], parent=None):
        super().__init__(parent)
        self.method_specs = method_specs
        self.controller = TimelineController(parent=self)
        self.tile_store = AudioStrengthTileStore()
        self.method_rows = []
        self._processed_ranges: list[VadTimeRange] = []
        self._active_ranges: list[VadTimeRange] = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        ruler_row = QHBoxLayout()
        ruler_row.setContentsMargins(10, 0, 10, 0)
        ruler_row.setSpacing(10)
        ruler_row.addSpacing(CONTROL_PANEL_WIDTH)
        self.ruler_widget = TimelineRulerWidget(self.controller)
        ruler_row.addWidget(self.ruler_widget, stretch=1)
        layout.addLayout(ruler_row)

        for method_spec in self.method_specs:
            row = VadMethodRow(
                controller=self.controller,
                tile_store=self.tile_store,
                method_spec=method_spec,
                vad_intervals=[],
            )
            self.method_rows.append(row)
            layout.addWidget(row)

        scrollbar_row = QHBoxLayout()
        scrollbar_row.setContentsMargins(10, 0, 10, 0)
        scrollbar_row.setSpacing(10)
        scrollbar_row.addSpacing(CONTROL_PANEL_WIDTH)
        self.scrollbar = QScrollBar(Qt.Horizontal)
        scrollbar_row.addWidget(self.scrollbar, stretch=1)
        layout.addLayout(scrollbar_row)

        self.scrollbar.valueChanged.connect(self.controller.set_offset_px)
        self.controller.scrollbar_state_changed.connect(self._sync_scrollbar_state)

        self._sync_scrollbar_state(
            self.controller.offset_px,
            self.controller.max_offset_px,
            self.controller.viewport_width_px,
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.controller.set_viewport_width(self.ruler_widget.width())

    def reset_for_media(self, duration_sec: float):
        self.tile_store.clear()
        self.controller.set_duration(duration_sec)
        self.controller.reset_view()
        self._processed_ranges = []
        self._active_ranges = []

        for row, method_spec in zip(self.method_rows, self.method_specs):
            row.track_widget.confirmed_cuts = []
            row.track_widget.set_blade_mode(False)
            row.control_panel.set_manual_checked(False)
            row.control_panel.set_auto_checked(False)
            if method_spec.method_key == "silero":
                row.track_widget.set_vad_intervals([])
            else:
                row.track_widget.set_vad_intervals(
                    _build_placeholder_intervals(method_spec.method_key, duration_sec)
                )
        self._update_all_tracks()

    def set_audio_status_message(self, status_message: str):
        self.tile_store.set_status_message(status_message)
        self._update_all_tracks()

    def set_audio_strength_data(self, strength_series, peak_value=None):
        self.tile_store.set_strength_series(strength_series, peak_value=peak_value)
        self._update_all_tracks()

    def apply_audio_strength_patch(self, amplitude_patch: AudioStrengthPatch, peak_value=None):
        self.tile_store.apply_strength_patch(
            start_index=amplitude_patch.start_index,
            values=amplitude_patch.values,
            peak_value=peak_value,
        )
        self._update_all_tracks()

    def set_audio_peak(self, peak_value: float | None):
        self.tile_store.set_peak_value(peak_value)
        self._update_all_tracks()

    def set_processing_state(
        self,
        processed_ranges: list[VadTimeRange],
        active_ranges: list[VadTimeRange],
    ):
        self._processed_ranges = list(processed_ranges)
        self._active_ranges = list(active_ranges)
        if not self.tile_store.has_strength_series():
            sample_count = max(
                int(math.ceil(self.controller.duration_sec * self.controller.samples_per_second)),
                1,
            )
            self.tile_store.initialize_empty_series(sample_count)
        for row in self.method_rows:
            row.track_widget.set_processing_state(self._processed_ranges, self._active_ranges)
        self._update_all_tracks()

    def clear_active_processing(self):
        self.set_processing_state(self._processed_ranges, [])

    def set_method_vad_intervals(self, method_key: str, vad_intervals: list[VadInterval]):
        for row in self.method_rows:
            if row.method_spec.method_key == method_key:
                row.track_widget.set_vad_intervals(vad_intervals)
                break
        self._update_all_tracks()

    def clear_timeline(self):
        self.tile_store.clear()
        self.controller.set_duration(7200.0)
        self.controller.reset_view()
        self._processed_ranges = []
        self._active_ranges = []
        for row in self.method_rows:
            row.track_widget.confirmed_cuts = []
            row.track_widget.set_blade_mode(False)
            row.control_panel.set_manual_checked(False)
            row.control_panel.set_auto_checked(False)
            row.track_widget.set_vad_intervals([])
            row.track_widget.set_processing_state([], [])
        self.tile_store.set_status_message("Waiting for media broadcast")
        self._update_all_tracks()

    def hide_slice_tool_panels(self):
        for row in self.method_rows:
            row.hide_slice_tool_panel()

    def _sync_scrollbar_state(self, value: int, maximum: int, page_step: int):
        self.scrollbar.blockSignals(True)
        self.scrollbar.setRange(0, maximum)
        self.scrollbar.setPageStep(max(page_step, 1))
        self.scrollbar.setSingleStep(50)
        self.scrollbar.setValue(value)
        self.scrollbar.blockSignals(False)

    def _update_all_tracks(self):
        self.ruler_widget.update()
        for row in self.method_rows:
            row.track_widget.update()


def _choose_tick_interval(visible_duration_sec: float) -> float:
    candidates = [0.5, 1.0, 2.0, 5.0, 10.0, 15.0, 30.0, 60.0, 120.0, 300.0]
    for candidate in candidates:
        if visible_duration_sec / candidate <= 12:
            return candidate
    return 600.0


def _format_time_label(seconds: float) -> str:
    total_ms = max(int(seconds * 1000), 0)
    total_seconds = total_ms // 1000
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _slice_tool_button_stylesheet() -> str:
    return """
        QPushButton {
            padding: 4px 8px;
        }
        QPushButton:checked {
            background-color: #D0E8FF;
            border: 1px solid #4A90D9;
            border-radius: 3px;
        }
        QPushButton:disabled {
            color: #999999;
        }
    """


def _slice_tool_panel_stylesheet() -> str:
    return """
        QFrame#sliceToolPanel {
            background-color: #ffffff;
            border: 1px solid #cfcfcf;
            border-radius: 4px;
        }
        QLabel#sliceToolNote {
            color: #5f6f85;
            font-size: 11px;
        }
    """


def _build_placeholder_intervals(method_key: str, duration_sec: float) -> list[VadInterval]:
    duration_sec = max(duration_sec, 1.0)
    method_seed = max(sum(ord(ch) for ch in method_key) % 9, 1)
    intervals = []
    cursor = method_seed * 0.7

    while cursor < duration_sec:
        speech_length = 1.2 + ((method_seed * 11 + int(cursor * 10)) % 40) / 10.0
        gap_length = 0.6 + ((method_seed * 7 + int(cursor * 8)) % 18) / 10.0
        end_sec = min(cursor + speech_length, duration_sec)
        intervals.append(
            VadInterval(
                start_sec=cursor,
                end_sec=end_sec,
                label=f"{method_key}-speech",
            )
        )
        cursor = end_sec + gap_length

    return intervals
