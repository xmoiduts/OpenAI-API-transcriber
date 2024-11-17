from PyQt5.QtWidgets import (QFrame, QToolTip, QMenu, QWidgetAction, 
                           QLabel, QPushButton, QLineEdit, QHBoxLayout, 
                           QVBoxLayout, QWidget)
from PyQt5.QtCore import Qt, QRectF, QEvent
from PyQt5.QtGui import QPainter, QPen, QColor, QFont
from .draggable_label import DraggableLabel

class SegmentBar(QFrame):
    def __init__(self, parent=None, mode="time_slicer"):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.setStyleSheet("background-color: #d3d3d3; border-radius: 5px;")
        self.segments = [] # list of (start: int?, duration: int?)
        self.setMouseTracking(True)
        self.hovered_segment = -1
        self.mode = mode
        self.segment_status = {}  # For transcription status
        self.segment_start_offsets = []  # List of time offsets (int) in seconds

    def get_hms_editor_stylesheet(self):
        return """
            QMenu {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 4px;
                font-family: Arial, sans-serif;
            }
            QMenu::item {
                padding: 4px 20px;
                color: #333333;
            }
            QMenu::item:selected {
                background-color: #e0e0e0;
            }
            QMenu::separator {
                height: 1px;
                background-color: #d0d0d0;
                margin: 4px 0px;
            }
            QWidget#hms_editor {
                background-color: #f0f0f0;
                padding: 8px;
            }
            QLabel {
                background-color: #f0f0f0;
                color: #333333;
                font-size: 14px;
            }
            QPushButton#reset_button {
                background-color: #FFB3B3;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton#reset_button:hover {
                background-color: #FFA0A0;
            }
            QLineEdit {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 4px;
                color: #333333;
                font-size: 14px;
                font-weight: bold;
            }
            QLineEdit:focus {
                border: 1px solid #4CAF50;
            }
            QToolTip {
                background-color: #f0f0f0;
                color: #333333;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 8px;
                font-size: 14px;
            }
        """

    def set_segments(self, segments):
        self.segments = segments
        self.segment_start_offsets = [start for (start, duration) in segments]
        self.update()

    def set_segment_status(self, segment_status):
        self.segment_status = segment_status
        self.update()

    def seconds_to_hms(self, seconds):
        """Convert seconds to HMS format"""
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return h, m, s

    def hms_to_seconds(self, h, m, s):
        """Convert HMS to seconds"""
        return h * 3600 + m * 60 + s

    def get_segment_start_offset_hms(self, segment_index):
        """Get offset for a segment in HMS format"""
        if 0 <= segment_index < len(self.segment_start_offsets):
            seconds = self.segment_start_offsets[segment_index]
            return self.seconds_to_hms(seconds)
        return 0, 0, 0

    def set_segment_start_offset_hms(self, segment_index, h, m, s):
        """Set offset for a segment using HMS format"""
        if 0 <= segment_index < len(self.segment_start_offsets):
            self.segment_start_offsets[segment_index] = self.hms_to_seconds(h, m, s)
            self.update()

    def is_valid_segment_time(self, segment_index, seconds):
        # 检查给定的时间是否在segment的有效范围内
        if segment_index < 0 or segment_index >= len(self.segments):
            return False
            
        # 获取当前segment的开始和结束时间
        start_time = self.segments[segment_index][0]
        duration = self.segments[segment_index][1]
        end_time = start_time + duration
        
        # 如果是第一个segment，只检查上限
        if segment_index == 0:
            return seconds <= end_time
        
        # 获取前一个segment的结束时间作为下限
        prev_start, prev_duration = self.segments[segment_index - 1]
        prev_end = prev_start + prev_duration
        
        return prev_end <= seconds <= end_time

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

            # Draw start delimiter line if the actual transcribe start time is altered.
            offset_seconds = self.segment_start_offsets[i]
            if offset_seconds > start and self.is_valid_segment_time(i, offset_seconds):
                relative_offset = offset_seconds - start
                offset_x = round(x_prev + (relative_offset / duration) * segment_width)

                # Draw green line
                painter.setPen(QPen(QColor("#4CAF50"), 2))  # Saturated red
                painter.drawLine(offset_x, 5, offset_x, height - 5)
                
                # Draw cross mark in the area between segment start and invalid offset
                cross_rect = QRectF(x_prev + 2, 5, offset_x - x_prev - 2, height - 10)
                painter.setPen(QPen(QColor("#FF4444"), 1))
                painter.drawLine(cross_rect.topLeft(), cross_rect.bottomRight())
                painter.drawLine(cross_rect.topRight(), cross_rect.bottomLeft())

            if i == self.hovered_segment:
                painter.setPen(QPen(QColor("#FF4500"), 1))
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
                h, m, s = self.get_segment_start_offset_hms(i)
                tooltip_text = f"Start: {start}s, Duration: {duration}s"
                if self.mode == "transcription":
                    tooltip_text += f"\nTranscribe from: {h:02d}:{m:02d}:{s:02d}"
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

    def create_help_icon(self, parent=None):
        """Create a circular help icon with question mark"""
        label = QLabel(parent)
        label.setFixedSize(16, 16)
        label.setStyleSheet("""
            QLabel {
                background-color: transparent;
                color: inherit;
                font-family: inherit;
            }
        """)
        label.setToolTip(
            "Adjust the start time to optimize Whisper model transcription.\n"
            "When audio begins with music or non-speech content,\n"
            "the model may generate inaccurate text.\n"
            "By adjusting the start time, you can skip these parts\n"
            "and begin transcription from actual speech."
        )
        
        def paintEvent(event):
            painter = QPainter(label)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 使用父组件的背景色和文本色
            parent_palette = label.parent().palette()
            bg_color = parent_palette.color(label.parent().backgroundRole())
            text_color = parent_palette.color(label.parent().foregroundRole())
            
            # Draw circle
            painter.setPen(QPen(text_color, 1))
            painter.setBrush(bg_color)
            painter.drawEllipse(0, 0, 15, 15)
            
            # Draw question mark
            painter.setPen(text_color)
            painter.setFont(QFont(label.parent().font()))
            painter.drawText(0, 0, 15, 15, Qt.AlignCenter, "?")
        
        label.paintEvent = paintEvent
        return label

    # for context menu only
    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            # 如果点击的是 HMS widget 的空白区域，阻止事件传播
            if obj == self.hms_widget and not any(child.underMouse() for child in obj.findChildren((QLineEdit, QPushButton))):
                return True
        return super().eventFilter(obj, event)
    def contextMenuEvent(self, event):
        # Right-Click menu, allowing users to:
        #   Manually edit transcription start time for one segment
        #   ... toggle transcribe status to skip/redo transcription? ...
        if self.mode != "transcription":
            return
            
        # Get segment index under cursor
        x = event.x()
        width = self.width()
        total_duration = sum(duration for _, duration in self.segments)
        
        current_segment = -1
        x_temp = x
        for i, (start, duration) in enumerate(self.segments):
            segment_width = (duration / total_duration) * width
            if x_temp <= segment_width:
                current_segment = i
                break
            x_temp -= segment_width
        
        if current_segment == -1:
            return
            
        menu = QMenu(self)
        menu.setStyleSheet(self.get_hms_editor_stylesheet())
        
        # Add placeholder items
        menu.addAction("Placeholder 1")
        menu.addSeparator()
        
        # Create HMS editor widget
        hms_widget = QWidget()
        self.hms_widget = hms_widget  # Store reference for event filter
        hms_widget.setObjectName("hms_editor")
        hms_widget.installEventFilter(self)
        vbox = QVBoxLayout(hms_widget)

        # First row
        top_row = QHBoxLayout()
        label = QLabel("Transcribe from")
        help_icon = self.create_help_icon(hms_widget)
        reset_btn = QPushButton("Reset")
        reset_btn.setObjectName("reset_button")
        top_row.addWidget(label)
        top_row.addWidget(help_icon)
        top_row.addStretch()
        top_row.addWidget(reset_btn)
        vbox.addLayout(top_row)
        
        # Second row - HMS inputs
        bottom_row = QHBoxLayout()
        h_input = QLineEdit()
        m_input = QLineEdit()
        s_input = QLineEdit()
        
        # Apply some additional styling to input boxes
        for input_box in (h_input, m_input, s_input):
            input_box.setFixedWidth(40)
            input_box.setAlignment(Qt.AlignCenter)
            # input_box.setStyleSheet("""
            #     QLineEdit {
            #         font-size: 14px;
            #         font-weight: bold;
            #     }
            # """)
        
        h, m, s = self.get_segment_start_offset_hms(current_segment)
        h_input.setText(str(h))
        m_input.setText(str(m))
        s_input.setText(str(s))
        
        bottom_row.addWidget(h_input)
        bottom_row.addWidget(DraggableLabel("H", h_input))
        bottom_row.addWidget(m_input)
        bottom_row.addWidget(DraggableLabel("M", m_input))
        bottom_row.addWidget(s_input)
        bottom_row.addWidget(DraggableLabel("S", s_input))
        bottom_row.addStretch()
        
        vbox.addLayout(bottom_row)
        
        # Handle reset button
        def on_reset():
            start, _ = self.segments[current_segment]
            h, m, s = self.seconds_to_hms(start)
            h_input.setText(str(h))
            m_input.setText(str(m))
            s_input.setText(str(s))
        
        reset_btn.clicked.connect(on_reset)
        
        # Handle HMS input changes
        def on_hms_changed():
            try:
                h = int(h_input.text() or 0)
                m = int(m_input.text() or 0)
                s = int(s_input.text() or 0)
                total_seconds = self.hms_to_seconds(h, m, s)
                
                # 检查时间是否有效
                is_valid = self.is_valid_segment_time(current_segment, total_seconds)
                
                # 设置输入框样式
                color = "#333333" if is_valid else "#FF0000"
                for input_box in (h_input, m_input, s_input):
                    input_box.setStyleSheet(f"color: {color};")
                    
                # 无论是否有效都更新offset并触发重绘
                self.set_segment_start_offset_hms(current_segment, h, m, s)
                self.update()  # 确保重绘
                    
            except ValueError:
                pass
        
        for input_box in (h_input, m_input, s_input):
            input_box.textChanged.connect(on_hms_changed)
        
        # Add HMS widget to menu
        widget_action = QWidgetAction(menu)
        widget_action.setDefaultWidget(hms_widget)
        menu.addAction(widget_action)
        
        # Add more placeholder items
        menu.addSeparator()
        menu.addAction("Placeholder 2")
        
        menu.exec_(event.globalPos())