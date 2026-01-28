"""
Task Card Widget - Reusable card component for sentence builder tasks.

Each card contains:
- Header with task name
- Prompt template editor
- User input text area
- Task-specific controls (subclass responsibility)
- Start button with hover effect
"""

from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QPlainTextEdit, QSizePolicy, QWidget, QComboBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QEvent
from PyQt5.QtGui import QFont
from pathlib import Path
from typing import Optional, Callable

try:
    # Optional (used for reading task defaults from config.yaml)
    from chatbot_core.thinking_resolver import load_root_config, get_task_default_thinking_level, SUPPORTED_NORMALIZED_LEVELS
except Exception:
    load_root_config = None
    get_task_default_thinking_level = None
    SUPPORTED_NORMALIZED_LEVELS = ("auto", "no", "low", "mid", "high")


class TaskCard(QFrame):
    """Base task card widget for sentence builder tasks.
    
    Signals:
        start_clicked: Emitted when Start button is clicked
        start_hovered: Emitted when Start button hover state changes (True=enter, False=leave)
    """
    
    start_clicked = pyqtSignal()
    start_hovered = pyqtSignal(bool)  # True = hover enter, False = hover leave
    
    def __init__(
        self,
        task_name: str,
        task_key: str,
        prompt_file: Optional[str] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.task_name = task_name
        self.task_key = task_key
        self.prompt_file = prompt_file
        
        self.setObjectName("taskCard")
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        
        self.init_ui()
        self.apply_styles()
        
        # Load prompt if file specified
        if prompt_file:
            self.load_prompt(prompt_file)
    
    def init_ui(self):
        """Initialize the card UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # Header
        self.header = QLabel(self.task_name)
        self.header.setObjectName("taskCardHeader")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        self.header.setFont(header_font)
        layout.addWidget(self.header)
        
        # Prompt section
        prompt_label = QLabel("Prompt Template:")
        prompt_label.setObjectName("taskCardLabel")
        layout.addWidget(prompt_label)
        
        self.prompt_edit = QPlainTextEdit()
        self.prompt_edit.setObjectName("taskCardPrompt")
        self.prompt_edit.setPlaceholderText("Enter or load prompt template...")
        self.prompt_edit.setMinimumHeight(80)
        self.prompt_edit.setMaximumHeight(150)
        layout.addWidget(self.prompt_edit)
        
        # User input section
        user_label = QLabel("Additional Notes:")
        user_label.setObjectName("taskCardLabel")
        layout.addWidget(user_label)
        
        self.user_input = QPlainTextEdit()
        self.user_input.setObjectName("taskCardUserInput")
        self.user_input.setPlaceholderText("Add any specific instructions...")
        self.user_input.setMinimumHeight(40)
        self.user_input.setMaximumHeight(80)
        layout.addWidget(self.user_input)

        # Thinking level selector (per-task)
        thinking_container = QWidget()
        thinking_layout = QHBoxLayout(thinking_container)
        thinking_layout.setContentsMargins(0, 0, 0, 0)
        thinking_layout.setSpacing(6)

        thinking_label = QLabel("Thinking:")
        thinking_label.setStyleSheet("color: #666666; font-size: 13px;")
        thinking_layout.addWidget(thinking_label)

        self.thinking_combo = QComboBox()
        self.thinking_combo.setObjectName("thinkingLevelCombo")
        self.thinking_combo.setStyleSheet("""
            QComboBox#thinkingLevelCombo {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 2px 8px;
                min-width: 90px;
                font-size: 13px;
            }
            QComboBox#thinkingLevelCombo:hover {
                border-color: #b0b0b0;
            }
        """)

        # Populate defaults
        self.set_supported_thinking_levels(list(SUPPORTED_NORMALIZED_LEVELS))
        self._apply_default_thinking_level()

        thinking_layout.addWidget(self.thinking_combo)
        thinking_layout.addStretch()
        layout.addWidget(thinking_container)
        
        # Task-specific controls container (for subclasses)
        self.controls_container = QWidget()
        self.controls_layout = QVBoxLayout(self.controls_container)
        self.controls_layout.setContentsMargins(0, 0, 0, 0)
        self.controls_layout.setSpacing(8)
        layout.addWidget(self.controls_container)
        
        # Start button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.start_button = QPushButton("Start")
        self.start_button.setObjectName("taskCardStartButton")
        self.start_button.setMinimumWidth(100)
        self.start_button.setCursor(Qt.PointingHandCursor)
        self.start_button.clicked.connect(self._on_start_clicked)
        
        # Install event filter for hover detection
        self.start_button.installEventFilter(self)
        
        button_layout.addWidget(self.start_button)
        layout.addLayout(button_layout)
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
    
    def apply_styles(self):
        """Apply card styles."""
        self.setStyleSheet("""
            QFrame#taskCard {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            QLabel#taskCardHeader {
                color: #333333;
                padding: 4px 0;
            }
            QLabel#taskCardLabel {
                color: #666666;
                font-size: 13px;
            }
            QPlainTextEdit#taskCardPrompt, QPlainTextEdit#taskCardUserInput {
                background-color: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 8px;
                font-family: Consolas, Monaco, monospace;
                font-size: 13px;
            }
            QPlainTextEdit#taskCardPrompt:focus, QPlainTextEdit#taskCardUserInput:focus {
                border-color: #4a9eff;
            }
            QPushButton#taskCardStartButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton#taskCardStartButton:hover {
                background-color: #45a049;
            }
            QPushButton#taskCardStartButton:pressed {
                background-color: #3d8b40;
            }
        """)
    
    def eventFilter(self, obj, event):
        """Handle hover events for Start button."""
        if obj == self.start_button:
            if event.type() == QEvent.Enter:
                self.start_hovered.emit(True)
            elif event.type() == QEvent.Leave:
                self.start_hovered.emit(False)
        return super().eventFilter(obj, event)
    
    def _on_start_clicked(self):
        """Handle Start button click."""
        self.start_clicked.emit()
    
    def load_prompt(self, filepath: str):
        """Load prompt template from file."""
        try:
            path = Path(filepath)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    self.prompt_edit.setPlainText(f.read())
            else:
                self.prompt_edit.setPlainText(f"# Prompt file not found: {filepath}")
        except Exception as e:
            self.prompt_edit.setPlainText(f"# Error loading prompt: {e}")
    
    def get_prompt(self) -> str:
        """Get the current prompt template."""
        return self.prompt_edit.toPlainText()
    
    def get_user_input(self) -> str:
        """Get the user's additional notes."""
        return self.user_input.toPlainText()
    
    def add_control(self, widget: QWidget):
        """Add a task-specific control widget."""
        self.controls_layout.addWidget(widget)
    
    def set_enabled(self, enabled: bool):
        """Enable/disable the card."""
        self.start_button.setEnabled(enabled)
        self.prompt_edit.setEnabled(enabled)
        self.user_input.setEnabled(enabled)
        if hasattr(self, "thinking_combo"):
            self.thinking_combo.setEnabled(enabled)

    def _apply_default_thinking_level(self):
        """
        Initialize thinking selector from config.yaml task default when available.
        """
        if load_root_config and get_task_default_thinking_level:
            try:
                root = load_root_config()
                default_level = get_task_default_thinking_level(root, self.task_key)
                if default_level and self._combo_has_value(default_level):
                    self.thinking_combo.setCurrentText(default_level)
                    return
            except Exception:
                pass

        # Fallback: assemble-sentence defaults to low, others to auto
        fallback = "low" if self.task_key == "assemble-sentence" else "auto"
        if self._combo_has_value(fallback):
            self.thinking_combo.setCurrentText(fallback)

    def _combo_has_value(self, value: str) -> bool:
        for i in range(self.thinking_combo.count()):
            if self.thinking_combo.itemText(i) == value:
                return True
        return False

    def get_thinking_level(self) -> str:
        """Get currently selected thinking level (normalized)."""
        if hasattr(self, "thinking_combo"):
            return self.thinking_combo.currentText().strip() or "auto"
        return "auto"

    def set_supported_thinking_levels(self, levels: list):
        """
        Update the thinking selector options.

        Policy:
        - If a level (e.g. 'no') is not supported, we hide it (remove from list).
        - Try to keep the current selection when possible.
        """
        if not hasattr(self, "thinking_combo"):
            return

        current = self.get_thinking_level()

        self.thinking_combo.blockSignals(True)
        try:
            self.thinking_combo.clear()
            for level in levels:
                self.thinking_combo.addItem(level)
            # preserve selection
            if current and self._combo_has_value(current):
                self.thinking_combo.setCurrentText(current)
            else:
                self._apply_default_thinking_level()
        finally:
            self.thinking_combo.blockSignals(False)


class MergeOverlapsCard(TaskCard):
    """Card for the merge overlaps task - merges overlapping timestamp regions from segmented transcription."""
    
    chars_changed = pyqtSignal(int)  # Emitted when chars per slice changes
    
    def __init__(self, parent: Optional[QWidget] = None):
        self._chars_per_slice = 10000
        self._min_chars = 1000
        self._max_chars = 100000
        self._drag_start_x = 0
        self._drag_start_value = 0
        self._is_dragging = False
        
        super().__init__(
            task_name="Merge Overlaps",
            task_key="merge_overlaps",
            prompt_file="prompts/sentence-rebuild/merge_overlaps.txt",
            parent=parent
        )
        
        self._init_slider_control()
    
    def _init_slider_control(self):
        """Initialize the drag slider control."""
        slider_container = QWidget()
        slider_layout = QHBoxLayout(slider_container)
        slider_layout.setContentsMargins(0, 4, 0, 4)
        
        label = QLabel("Chars per slice:")
        label.setStyleSheet("color: #666666; font-size: 13px;")
        slider_layout.addWidget(label)
        
        self.slider_label = QLabel(str(self._chars_per_slice))
        self.slider_label.setObjectName("mergeOverlapsSlider")
        self.slider_label.setStyleSheet("""
            QLabel#mergeOverlapsSlider {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 4px 12px;
                font-family: Consolas, Monaco, monospace;
                font-weight: bold;
                min-width: 60px;
            }
            QLabel#mergeOverlapsSlider:hover {
                background-color: #e8e8e8;
                border-color: #b0b0b0;
            }
        """)
        self.slider_label.setCursor(Qt.SizeHorCursor)  # <-> cursor
        self.slider_label.setMouseTracking(True)
        self.slider_label.installEventFilter(self)
        slider_layout.addWidget(self.slider_label)
        
        slider_layout.addStretch()
        self.add_control(slider_container)
    
    def eventFilter(self, obj, event):
        """Handle drag events for slider."""
        if hasattr(self, 'slider_label') and obj == self.slider_label:
            if event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    self._is_dragging = True
                    self._drag_start_x = event.globalX()
                    self._drag_start_value = self._chars_per_slice
                    return True
            elif event.type() == QEvent.MouseMove:
                if self._is_dragging:
                    delta_x = event.globalX() - self._drag_start_x
                    # 10 pixels = 1000 chars
                    delta_chars = (delta_x // 10) * 1000
                    new_value = self._drag_start_value + delta_chars
                    new_value = max(self._min_chars, min(self._max_chars, new_value))
                    if new_value != self._chars_per_slice:
                        self._chars_per_slice = new_value
                        self.slider_label.setText(str(new_value))
                        self.chars_changed.emit(new_value)
                    return True
            elif event.type() == QEvent.MouseButtonRelease:
                if event.button() == Qt.LeftButton and self._is_dragging:
                    self._is_dragging = False
                    return True
        
        return super().eventFilter(obj, event)
    
    def get_chars_per_slice(self) -> int:
        """Get the current chars per slice value."""
        return self._chars_per_slice
    
    def set_chars_per_slice(self, value: int):
        """Set the chars per slice value."""
        value = max(self._min_chars, min(self._max_chars, value))
        self._chars_per_slice = value
        if hasattr(self, 'slider_label'):
            self.slider_label.setText(str(value))


class CutpointCard(TaskCard):
    """Card for the cutpoint task - includes drag slider for lines per segment."""
    
    lines_changed = pyqtSignal(int)  # Emitted when lines per segment changes
    
    def __init__(self, parent: Optional[QWidget] = None):
        self._lines_per_segment = 3000
        self._min_lines = 100
        self._max_lines = 10000
        self._drag_start_x = 0
        self._drag_start_value = 0
        self._is_dragging = False
        
        super().__init__(
            task_name="Cutpoint",
            task_key="cutpoint",
            prompt_file="prompts/sentence-rebuild/cutpoint.txt",
            parent=parent
        )
        
        self._init_slider_control()
    
    def _init_slider_control(self):
        """Initialize the drag slider control."""
        slider_container = QWidget()
        slider_layout = QHBoxLayout(slider_container)
        slider_layout.setContentsMargins(0, 4, 0, 4)
        
        label = QLabel("Lines per segment:")
        label.setStyleSheet("color: #666666; font-size: 13px;")
        slider_layout.addWidget(label)
        
        self.slider_label = QLabel(str(self._lines_per_segment))
        self.slider_label.setObjectName("cutpointSlider")
        self.slider_label.setStyleSheet("""
            QLabel#cutpointSlider {
                background-color: #f0f0f0;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 4px 12px;
                font-family: Consolas, Monaco, monospace;
                font-weight: bold;
                min-width: 60px;
            }
            QLabel#cutpointSlider:hover {
                background-color: #e8e8e8;
                border-color: #b0b0b0;
            }
        """)
        self.slider_label.setCursor(Qt.SizeHorCursor)  # <-> cursor
        self.slider_label.setMouseTracking(True)
        self.slider_label.installEventFilter(self)
        slider_layout.addWidget(self.slider_label)
        
        slider_layout.addStretch()
        self.add_control(slider_container)
    
    def eventFilter(self, obj, event):
        """Handle drag events for slider."""
        # Check if slider_label exists (it's created after super().__init__)
        if hasattr(self, 'slider_label') and obj == self.slider_label:
            if event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    self._is_dragging = True
                    self._drag_start_x = event.globalX()
                    self._drag_start_value = self._lines_per_segment
                    return True
            elif event.type() == QEvent.MouseMove:
                if self._is_dragging:
                    delta_x = event.globalX() - self._drag_start_x
                    # 10 pixels = 100 lines
                    delta_lines = (delta_x // 10) * 100
                    new_value = self._drag_start_value + delta_lines
                    new_value = max(self._min_lines, min(self._max_lines, new_value))
                    if new_value != self._lines_per_segment:
                        self._lines_per_segment = new_value
                        self.slider_label.setText(str(new_value))
                        self.lines_changed.emit(new_value)
                    return True
            elif event.type() == QEvent.MouseButtonRelease:
                if event.button() == Qt.LeftButton and self._is_dragging:
                    self._is_dragging = False
                    return True
        
        return super().eventFilter(obj, event)
    
    def get_lines_per_segment(self) -> int:
        """Get the current lines per segment value."""
        return self._lines_per_segment
    
    def set_lines_per_segment(self, value: int):
        """Set the lines per segment value."""
        value = max(self._min_lines, min(self._max_lines, value))
        self._lines_per_segment = value
        self.slider_label.setText(str(value))
    
    def set_max_lines(self, max_lines: int):
        """Set the maximum lines based on file size."""
        self._max_lines = max(self._min_lines, max_lines)


class AssembleCard(TaskCard):
    """Card for the assemble sentence task - includes editable line range table."""
    
    def __init__(self, parent: Optional[QWidget] = None):
        self._line_ranges: list = []  # List of (start, end) tuples
        
        super().__init__(
            task_name="Assemble Sentence",
            task_key="assemble-sentence",
            prompt_file="prompts/sentence-rebuild/assemble.txt",
            parent=parent
        )
        
        self._init_range_table()
    
    def _init_range_table(self):
        """Initialize the line range table."""
        from PyQt5.QtWidgets import QScrollArea, QLineEdit
        
        # Container with scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(150)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #fafafa;
            }
        """)
        
        self.ranges_container = QWidget()
        self.ranges_layout = QVBoxLayout(self.ranges_container)
        self.ranges_layout.setContentsMargins(8, 8, 8, 8)
        self.ranges_layout.setSpacing(4)
        
        scroll.setWidget(self.ranges_container)
        self.add_control(scroll)
        
        # Add button
        add_btn_container = QWidget()
        add_btn_layout = QHBoxLayout(add_btn_container)
        add_btn_layout.setContentsMargins(0, 4, 0, 0)
        
        self.add_range_btn = QPushButton("+")
        self.add_range_btn.setObjectName("addRangeButton")
        self.add_range_btn.setFixedSize(30, 30)
        self.add_range_btn.setStyleSheet("""
            QPushButton#addRangeButton {
                background-color: #e8e8e8;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton#addRangeButton:hover {
                background-color: #d8d8d8;
            }
        """)
        self.add_range_btn.clicked.connect(self._add_range_row)
        add_btn_layout.addWidget(self.add_range_btn)
        add_btn_layout.addStretch()
        
        self.add_control(add_btn_container)
        
        # Add initial row
        self._add_range_row(1, 1000)
    
    def _add_range_row(self, start: int = None, end: int = None):
        """Add a new line range row."""
        from PyQt5.QtWidgets import QLineEdit
        
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)
        
        # "line" label
        line_label = QLabel("line")
        line_label.setStyleSheet("color: #666666; font-size: 13px;")
        row_layout.addWidget(line_label)
        
        # Start input
        start_input = QLineEdit()
        start_input.setObjectName("rangeInput")
        start_input.setFixedWidth(60)
        start_input.setPlaceholderText("start")
        if start is not None:
            start_input.setText(str(start))
        start_input.setStyleSheet("""
            QLineEdit#rangeInput {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                padding: 2px 4px;
                font-family: Consolas, Monaco, monospace;
            }
        """)
        row_layout.addWidget(start_input)
        
        # Dash
        dash_label = QLabel("-")
        dash_label.setStyleSheet("color: #666666;")
        row_layout.addWidget(dash_label)
        
        # End input
        end_input = QLineEdit()
        end_input.setObjectName("rangeInput")
        end_input.setFixedWidth(60)
        end_input.setPlaceholderText("end")
        if end is not None:
            end_input.setText(str(end))
        end_input.setStyleSheet("""
            QLineEdit#rangeInput {
                background-color: white;
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                padding: 2px 4px;
                font-family: Consolas, Monaco, monospace;
            }
        """)
        row_layout.addWidget(end_input)
        
        row_layout.addStretch()
        
        # Remove button
        remove_btn = QPushButton("-")
        remove_btn.setObjectName("removeRangeButton")
        remove_btn.setFixedSize(24, 24)
        remove_btn.setStyleSheet("""
            QPushButton#removeRangeButton {
                background-color: #ffcccc;
                border: 1px solid #ffaaaa;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton#removeRangeButton:hover {
                background-color: #ffbbbb;
            }
        """)
        remove_btn.clicked.connect(lambda: self._remove_range_row(row_widget))
        row_layout.addWidget(remove_btn)
        
        # Store references
        row_widget.start_input = start_input
        row_widget.end_input = end_input
        
        self.ranges_layout.addWidget(row_widget)
    
    def _remove_range_row(self, row_widget: QWidget):
        """Remove a line range row."""
        # Keep at least one row
        if self.ranges_layout.count() <= 1:
            return
        
        self.ranges_layout.removeWidget(row_widget)
        row_widget.deleteLater()
    
    def get_line_ranges(self) -> list:
        """Get all line ranges as list of (start, end) tuples."""
        ranges = []
        for i in range(self.ranges_layout.count()):
            item = self.ranges_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if hasattr(widget, 'start_input') and hasattr(widget, 'end_input'):
                    try:
                        start = int(widget.start_input.text())
                        end = int(widget.end_input.text())
                        ranges.append((start, end))
                    except ValueError:
                        pass  # Skip invalid entries
        return ranges
    
    def set_line_ranges(self, ranges: list):
        """Set line ranges from list of (start, end) tuples."""
        # Clear existing rows
        while self.ranges_layout.count() > 0:
            item = self.ranges_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add new rows
        for start, end in ranges:
            self._add_range_row(start, end)
        
        # Ensure at least one row
        if not ranges:
            self._add_range_row()
