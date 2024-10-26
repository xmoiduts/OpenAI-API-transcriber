from PyQt5.QtWidgets import QFrame, QToolTip
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPainter, QPen, QColor

class SegmentBar(QFrame):
    def __init__(self, parent=None, mode="time_slicer"):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.setStyleSheet("background-color: #d3d3d3; border-radius: 5px;")
        self.segments = []
        self.setMouseTracking(True)
        self.hovered_segment = -1
        self.mode = mode
        self.segment_status = {}  # For transcription status

    def set_segments(self, segments):
        self.segments = segments
        self.update()

    def set_segment_status(self, segment_status):
        self.segment_status = segment_status
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.segments:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        total_duration = sum(duration for _, duration in self.segments)
        width = self.width()
        height = self.height()

        x_prev = 0
        for i, (start, duration) in enumerate(self.segments):
            x = round((sum(d for _, d in self.segments[:i+1]) / total_duration) * width)
            segment_width = x - x_prev

            if i > 0:
                painter.setPen(QPen(QColor("#a0a0a0"), 2))
                painter.drawLine(x_prev, 0, x_prev, height)

            segment_rect = QRectF(x_prev + 2, 5, segment_width - 4, height - 10)
            painter.setPen(Qt.NoPen)
            
            if self.mode == "time_slicer":
                painter.setBrush(QColor("#FFA500"))
            elif self.mode == "transcription":
                status = self.segment_status.get(i, "pending")
                color = self.get_status_color(status)
                painter.setBrush(QColor(color))

            painter.drawRoundedRect(segment_rect, 5, 5)

            if i == self.hovered_segment:
                painter.setPen(QPen(QColor("#FF4500"), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(segment_rect, 5, 5)

            x_prev = x

    def get_status_color(self, status):
        colors = {
            "pending": "#FFFFFF",  # White
            "in_progress": "#4169E1",  # Royal Blue
            "completed": "#32CD32",  # Lime Green
            "error": "#FF0000"  # Red
        }
        return colors.get(status, "#FFFFFF")

    def mouseMoveEvent(self, event):
        if not self.segments:
            return

        total_duration = sum(duration for _, duration in self.segments)
        width = self.width()
        x = event.x()

        cumulative_duration = 0
        for i, (start, duration) in enumerate(self.segments):
            segment_width = (duration / total_duration) * width
            if x <= segment_width:
                self.hovered_segment = i
                tooltip_text = f"Start: {start}s, Duration: {duration}s"
                if self.mode == "transcription":
                    status = self.segment_status.get(i, "pending")
                    tooltip_text += f"\nStatus: {status.capitalize()}"
                QToolTip.showText(event.globalPos(), tooltip_text)
                self.update()
                break
            x -= segment_width
            cumulative_duration += duration
        else:
            self.hovered_segment = -1
            self.update()

        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.hovered_segment = -1
        self.update()
        super().leaveEvent(event)