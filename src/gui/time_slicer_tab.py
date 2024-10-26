from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, 
    QFileDialog, QToolTip, QApplication
)
from PyQt5.QtCore import Qt, QTimer, QEvent, QRectF
from PyQt5.QtGui import QCursor, QPainter, QPen, QColor
from .tab_interface import TabInterface
from src.time_slicer.time_slicer import get_time_slices
from src.time_slicer.probe_media_file import probe_media_file
from .segment_bar import SegmentBar
import os
import sys
import subprocess
from PyQt5 import sip
from .flying_message import show_flying_message

def get_stylesheet():
    return """
        QMainWindow, QWidget {
            background-color: #f0f0f0;
            font-family: Arial, sans-serif;
        }
        QLabel, QPushButton, QTabBar::tab {
            color: #333333;
            font-size: 14px;
        }
        QPushButton {
            background-color: #4CAF50;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
        QPushButton:disabled {
            background-color: #a0a0a0;
            color: #d0d0d0;
        }
        QLabel#drop_label {
            border: 2px dashed #aaa;
            padding: 20px;
            background-color: #ffffff;
            border-radius: 8px;
            font-size: 18px;  /* Increased font size for drop label */
            font-weight: bold;  /* Optional: make the text bold */
            color: #888888;  /* Lighter font color */
        }
        QPushButton#open_file_button {
            background-color: #4CAF50;
            color: white;
        }
        QPushButton#open_file_button:hover {
            background-color: #45a049;
        }
        QPushButton#reload_button {
            background-color: #FFB3B3;
            color: white;
            font-weight: bold;
        }
        QPushButton#reload_button:hover {
            background-color: #FFA0A0;
        }
        QTabWidget::pane {
            border: 1px solid #d0d0d0;
            border-radius: 4px;
        }
        QTabBar::tab {
            background-color: #e0e0e0;
            border: 1px solid #c0c0c0;
            border-bottom-color: #d0d0d0;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            padding: 2px 5px;  /* Reduced padding to decrease height */
            margin-right: 2px;
        }
        QTabBar::tab:selected, QTabBar::tab:hover {
            background-color: #f0f0f0;
        }
        QTabBar::tab:selected {
            border-bottom-color: #f0f0f0;
        }
    """

"""
class SegmentBar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.setStyleSheet("background-color: #d3d3d3; border-radius: 5px;")
        self.segments = []
        self.setMouseTracking(True)
        self.hovered_segment = -1

    def set_segments(self, segments):
        self.segments = segments
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
            painter.setBrush(QColor("#FFA500"))
            painter.drawRoundedRect(segment_rect, 5, 5)

            if i == self.hovered_segment:
                painter.setPen(QPen(QColor("#FF4500"), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(segment_rect, 5, 5)

            x_prev = x

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
                QToolTip.showText(event.globalPos(), f"Start: {start}s, Duration: {duration}s")
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
"""

# class FlyingLabel(QLabel):
#     def __init__(self, parent=None):
#         super().__init__(parent)
#         self.setAlignment(Qt.AlignCenter)
#         self.setStyleSheet("""
#             background-color: rgba(0, 0, 0, 0);
#             color: rgba(255, 255, 255, 0);
#             border-radius: 10px;
#             padding: 5px;
#         """)
#         self.setWordWrap(True)
#         self.timer = QTimer(self)
#         self.timer.timeout.connect(self.animate)
#         self.opacity = 0.0
#         self.y_position = 0
#         self.animation_state = "fly_in"

#     def animate(self):
#         if self.animation_state == "fly_in":
#             self.opacity = min(1.0, self.opacity + 0.1)
#             self.y_position = max(self.target_y, self.y_position - 2)
#             self.move(self.x(), int(self.y_position))
#             self.update_style()
            
#             if self.opacity >= 1.0 and self.y_position <= self.target_y:
#                 self.animation_state = "stay"
#                 self.timer.stop()
#                 self.stay_timer.start()
        
#         elif self.animation_state == "fade_out":
#             self.opacity = max(0.0, self.opacity - 0.1)
#             self.update_style()
            
#             if self.opacity <= 0:
#                 self.hide()
#                 self.timer.stop()

#     def update_style(self):
#         self.setStyleSheet(f"""
#             background-color: rgba(0, 0, 0, {int(180 * self.opacity)});
#             color: rgba(255, 255, 255, {int(255 * self.opacity)});
#             border-radius: 10px;
#             padding: 5px;
#         """)

#     def start_fade_out(self):
#         self.animation_state = "fade_out"
#         self.timer.start(16)
# 

class TimeSlicerTab(TabInterface):
    def __init__(self):
        super().__init__("Time Slicer")
        self.setAcceptDrops(True)
        self.current_file_path = ""
        self.file_duration = 0
        self.file_audio_bitrate = 0
        self.current_flying_label = None

        self.init_ui()
        self.setStyleSheet(get_stylesheet())

    def init_ui(self):
        layout = QVBoxLayout()
        
        self.drop_label = QLabel("Drag and drop a media file here")
        self.drop_label.setObjectName("drop_label")
        self.drop_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.drop_label)

        file_button_layout = QHBoxLayout()
        self.open_file_button = QPushButton("Open File")
        self.open_file_button.clicked.connect(self.open_file_dialog)
        self.open_file_button.setObjectName("open_file_button")

        self.reload_button = QPushButton("Reload")
        self.reload_button.setToolTip("Reload Application")
        self.reload_button.setObjectName("reload_button")
        self.reload_button.clicked.connect(self.reload_application)

        file_button_layout.addWidget(self.open_file_button, 4)
        file_button_layout.addWidget(self.reload_button, 1)
        layout.addLayout(file_button_layout)

        self.file_path_label = QLabel("File path: ")
        self.file_path_label.setWordWrap(True)
        layout.addWidget(self.file_path_label)

        self.file_length_label = QLabel("File length: ")
        self.file_length_label.setWordWrap(True)
        layout.addWidget(self.file_length_label)

        self.segment_bar = SegmentBar(mode="time_slicer")
        layout.addWidget(self.segment_bar)

        button_layout = QHBoxLayout()
        self.copy_full_path_button = self.create_copy_button("Copy Full Path", self.copy_full_path)
        self.copy_relative_path_button = self.create_copy_button("Copy Relative Path", self.copy_relative_path)
        self.copy_file_name_button = self.create_copy_button("Copy File Name", self.copy_file_name)

        button_layout.addWidget(self.copy_full_path_button)
        button_layout.addWidget(self.copy_relative_path_button)
        button_layout.addWidget(self.copy_file_name_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def create_copy_button(self, text, slot):
        button = QPushButton(text)
        button.clicked.connect(slot)
        button.installEventFilter(self)
        return button

    def eventFilter(self, obj, event):
        if isinstance(obj, QPushButton):
            if event.type() == QEvent.HoverEnter:
                preview_text = self.get_preview_text(obj.text())
                QToolTip.showText(QCursor.pos(), preview_text)
            elif event.type() == QEvent.HoverLeave:
                QToolTip.hideText()
        return super().eventFilter(obj, event)

    def get_preview_text(self, button_text):
        if not self.current_file_path:
            return "No file selected"
        
        if "Full Path" in button_text:
            return self.current_file_path
        elif "Relative Path" in button_text:
            try:
                relative_path = os.path.relpath(self.current_file_path)
                return relative_path.replace(os.path.sep, '/')
            except ValueError:
                return self.current_file_path
        elif "File Name" in button_text:
            return os.path.basename(self.current_file_path)
        return ""

    def copy_full_path(self):
        if self.current_file_path:
            QApplication.clipboard().setText(self.current_file_path)
            show_flying_message(self, f"Copied: {self.current_file_path}")
        else:
            show_flying_message(self, "No file selected")

    def copy_relative_path(self):
        if self.current_file_path:
            try:
                relative_path = os.path.relpath(self.current_file_path)
                unified_path = relative_path.replace(os.path.sep, '/')
                QApplication.clipboard().setText(unified_path)
                show_flying_message(self, f"Copied: {unified_path}")
            except ValueError:
                self.copy_full_path()
        else:
            show_flying_message(self, "No file selected")

    def copy_file_name(self):
        if self.current_file_path:
            file_name = os.path.basename(self.current_file_path)
            QApplication.clipboard().setText(file_name)
            show_flying_message(self, f"Copied: {file_name}")
        else:
            show_flying_message(self, "No file selected")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            self.current_file_path = files[0]
            self.update_file_info()

    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Media File", "medias", "Media Files (*.mp3 *.mp4 *.avi *.mov *.wav *.m4a)")
        if file_path:
            self.current_file_path = file_path
            self.file_path_label.setText(f"File path: {file_path}")
            self.drop_label.setText("File opened successfully from explorer!")
            self.parse_file_duration_and_bitrate(file_path)
            self.update_file_info()

    def parse_file_duration_and_bitrate(self, file_path):
        try:
            self.file_duration, self.file_audio_bitrate = probe_media_file(file_path)
            self.file_length_label.setText(
                f"File length: {self.file_duration:.2f} seconds, \
                Audio bitrate: {self.file_audio_bitrate/1000:.2f} kbps")
        except Exception as e:
            self.file_length_label.setText(f"Error: {str(e)}")

    def update_file_info(self):
        self.file_path_label.setText(f"File path: {self.current_file_path}")
        self.drop_label.setText("File processed successfully!")
        self.parse_file_duration_and_bitrate(self.current_file_path)
        self.update_segments()
        
        # Find the main window and update the transcription tab
        main_window = self.get_main_window()
        if main_window and hasattr(main_window, 'update_transcription_tab'):
            main_window.update_transcription_tab(
                self.current_file_path, self.file_duration, self.segment_bar.segments)
        else:
            print("Warning: Could not update transcription tab")

    def get_main_window(self):
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, 'update_transcription_tab'):
                return parent
            parent = parent.parent()
        return None

    def update_segments(self):
        if self.file_duration:
            slices = get_time_slices(self.file_duration, self.file_audio_bitrate)
            self.segment_bar.set_segments(slices)
        else:
            self.segment_bar.set_segments([])

    def reload_application(self):
        QApplication.quit()
        subprocess.Popen([sys.executable] + sys.argv)
