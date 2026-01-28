"""
Task Popup Window - Window for displaying LLM task execution progress and results.

Features:
- Header with task name
- Collapsible context section
- Real-time console log display
- Response area
- Close button
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextBrowser, QFrame, QSizePolicy, QWidget, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QFont, QTextCursor
from typing import Optional, Callable
import sys
from pathlib import Path
from contextlib import contextmanager

# Add src to path for imports
src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from chatbot_core import ChatCore


class CollapsibleSection(QWidget):
    """A collapsible widget section."""
    
    def __init__(self, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._is_collapsed = True
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header button
        self.toggle_btn = QPushButton(f"▶ {title}")
        self.toggle_btn.setObjectName("collapsibleHeader")
        self.toggle_btn.setStyleSheet("""
            QPushButton#collapsibleHeader {
                background-color: #f5f5f5;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                padding: 8px 12px;
                text-align: left;
                font-weight: bold;
                color: #555555;
            }
            QPushButton#collapsibleHeader:hover {
                background-color: #eeeeee;
            }
        """)
        self.toggle_btn.clicked.connect(self._toggle)
        layout.addWidget(self.toggle_btn)
        
        # Content area
        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content.hide()
        layout.addWidget(self.content)
        
        self._title = title
    
    def _toggle(self):
        """Toggle collapsed state."""
        self._is_collapsed = not self._is_collapsed
        self.content.setVisible(not self._is_collapsed)
        arrow = "▶" if self._is_collapsed else "▼"
        self.toggle_btn.setText(f"{arrow} {self._title}")
    
    def add_widget(self, widget: QWidget):
        """Add a widget to the content area."""
        self.content_layout.addWidget(widget)
    
    def set_expanded(self, expanded: bool):
        """Set the expanded state."""
        if expanded != (not self._is_collapsed):
            self._toggle()


class LLMWorker(QThread):
    """Worker thread for LLM operations."""
    
    chunk_received = pyqtSignal(str)
    response_complete = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    log_message = pyqtSignal(str)
    
    def __init__(self, chat_core: ChatCore, prompt: str, thinking_level: Optional[str] = None, task_key: Optional[str] = None):
        super().__init__()
        self.chat_core = chat_core
        self.prompt = prompt
        self.thinking_level = thinking_level
        self.task_key = task_key
        self._stop_requested = False

    class _SignalWriter:
        """
        File-like object to capture prints from providers and forward them
        into the popup's console log via a Qt signal.
        """

        def __init__(self, emit_line):
            self._emit_line = emit_line
            self._buf = ""

        def write(self, s):
            if not s:
                return 0
            self._buf += str(s)
            while "\n" in self._buf:
                line, self._buf = self._buf.split("\n", 1)
                line = line.rstrip("\r")
                if line.strip():
                    self._emit_line(line)
            return len(s)

        def flush(self):
            if self._buf.strip():
                self._emit_line(self._buf.rstrip("\r\n"))
            self._buf = ""

    @contextmanager
    def _capture_console(self):
        """
        Capture stdout/stderr during the request so provider-side print logs
        (e.g. OpenAIProvider Stream error) appear in the GUI popup log.
        """
        old_out, old_err = sys.stdout, sys.stderr
        writer = self._SignalWriter(lambda line: self.log_message.emit(line))
        try:
            sys.stdout = writer
            sys.stderr = writer
            yield
        finally:
            try:
                writer.flush()
            except Exception:
                pass
            sys.stdout, sys.stderr = old_out, old_err
    
    def run(self):
        """Execute LLM request."""
        try:
            with self._capture_console():
                self.log_message.emit("Starting LLM request...")
                full_response = ""

                gen = self.chat_core.send_stream(
                    self.prompt,
                    thinking_level=self.thinking_level,
                    task_key=self.task_key,
                )

                try:
                    while not self._stop_requested:
                        chunk = next(gen)
                        full_response += chunk
                        self.chunk_received.emit(chunk)
                except StopIteration as e:
                    if e.value:
                        full_response = e.value

                if not self._stop_requested:
                    self.log_message.emit("Response complete.")
                    self.response_complete.emit(full_response)

        except Exception as e:
            # Keep both provider print logs (captured) + the exception itself.
            self.error_occurred.emit(str(e))
    
    def request_stop(self):
        """Request the worker to stop."""
        self._stop_requested = True


class TaskPopupWindow(QDialog):
    """Popup window for task execution display.
    
    Shows:
    - Task header with optional line range info
    - Collapsible context section
    - Console log display
    - LLM response display
    """
    
    task_completed = pyqtSignal(bool, str)  # success, response
    gate_approved = pyqtSignal()  # Emitted when gate button is clicked
    
    def __init__(
        self,
        task_name: str,
        line_range: Optional[tuple] = None,
        parent: Optional[QWidget] = None,
        needs_approval: bool = False,
        slice_info: Optional[str] = None
    ):
        super().__init__(parent)
        self.task_name = task_name
        self.line_range = line_range
        self.needs_approval = needs_approval
        self.slice_info = slice_info
        
        self.chat_core: Optional[ChatCore] = None
        self._worker: Optional[LLMWorker] = None
        self._response_text = ""
        self._thinking_level: Optional[str] = None
        self._task_key: Optional[str] = None
        self._is_approved = not needs_approval  # Auto-approve if not needed
        self._pending_prompt = None
        self._pending_thinking_level = None
        self._pending_task_key = None
        
        title = f"Task: {task_name}"
        if slice_info:
            title += f" - {slice_info}"
        self.setWindowTitle(title)
        self.setMinimumSize(600, 500)
        self.setModal(False)  # Allow multiple windows
        
        self.init_ui()
        self.apply_styles()
    
    def init_ui(self):
        """Initialize the UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header_text = self.task_name
        if self.line_range:
            header_text += f" (lines {self.line_range[0]}-{self.line_range[1]})"
        
        header = QLabel(header_text)
        header.setObjectName("popupHeader")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header.setFont(header_font)
        layout.addWidget(header)
        
        # Context section (collapsible)
        self.context_section = CollapsibleSection("Context Sent to LLM")
        
        self.context_display = QTextBrowser()
        self.context_display.setObjectName("contextDisplay")
        self.context_display.setMinimumHeight(100)
        self.context_display.setMaximumHeight(200)
        self.context_section.add_widget(self.context_display)
        
        layout.addWidget(self.context_section)
        
        # Console log section
        log_label = QLabel("Console Log:")
        log_label.setStyleSheet("font-weight: bold; color: #555555;")
        layout.addWidget(log_label)
        
        self.log_display = QTextBrowser()
        self.log_display.setObjectName("logDisplay")
        self.log_display.setMinimumHeight(150)
        layout.addWidget(self.log_display)
        
        # Response section
        response_label = QLabel("LLM Response:")
        response_label.setStyleSheet("font-weight: bold; color: #555555;")
        layout.addWidget(response_label)
        
        self.response_display = QTextBrowser()
        self.response_display.setObjectName("responseDisplay")
        self.response_display.setMinimumHeight(150)
        layout.addWidget(self.response_display, 1)  # Stretch
        
        # Button row
        button_layout = QHBoxLayout()
        
        # Gate approval button (only show if needs approval)
        if self.needs_approval:
            self.approve_button = QPushButton("▶ Approve & Start")
            self.approve_button.setObjectName("approveButton")
            self.approve_button.clicked.connect(self._on_approve)
            button_layout.addWidget(self.approve_button)
        else:
            self.approve_button = None
        
        button_layout.addStretch()
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("stopButton")
        self.stop_button.clicked.connect(self._on_stop)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)
        
        self.close_button = QPushButton("Close")
        self.close_button.setObjectName("closeButton")
        self.close_button.clicked.connect(self.close)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
    
    def apply_styles(self):
        """Apply window styles."""
        self.setStyleSheet("""
            QDialog {
                background-color: #ffffff;
            }
            QLabel#popupHeader {
                color: #333333;
                padding-bottom: 8px;
                border-bottom: 2px solid #4CAF50;
            }
            QTextBrowser#contextDisplay, QTextBrowser#logDisplay, QTextBrowser#responseDisplay {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                padding: 8px;
                font-family: Consolas, Monaco, "Courier New", monospace;
                font-size: 11px;
                selection-background-color: #b3d9ff;
            }
            QTextBrowser#contextDisplay:focus, QTextBrowser#logDisplay:focus, QTextBrowser#responseDisplay:focus {
                border: 1px solid #1976d2;
            }
            QPushButton#stopButton {
                background-color: #ff6b6b;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton#stopButton:hover {
                background-color: #ee5a5a;
            }
            QPushButton#stopButton:disabled {
                background-color: #cccccc;
            }
            QPushButton#closeButton {
                background-color: #666666;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton#closeButton:hover {
                background-color: #555555;
            }
            QPushButton#approveButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }
            QPushButton#approveButton:hover {
                background-color: #45a049;
            }

            /* Light scrollbar styling (match app's light theme) */
            QDialog QScrollBar:vertical {
                background-color: #f0f0f0;
                width: 10px;
                margin: 0px;
            }
            QDialog QScrollBar::handle:vertical {
                background-color: #c0c0c0;
                min-height: 20px;
                border-radius: 5px;
                margin: 2px;
            }
            QDialog QScrollBar::handle:vertical:hover {
                background-color: #a0a0a0;
            }
            QDialog QScrollBar::add-line:vertical,
            QDialog QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
            }
            QDialog QScrollBar::add-page:vertical,
            QDialog QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
    
    def set_context(self, context: str):
        """Set the context text."""
        self.context_display.setPlainText(context)
    
    def log(self, message: str):
        """Add a log message."""
        cursor = self.log_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(message + "\n")
        self.log_display.setTextCursor(cursor)
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum()
        )
    
    def set_chat_core(self, chat_core: ChatCore):
        """Set the ChatCore instance to use."""
        self.chat_core = chat_core
    
    def execute_prompt(self, prompt: str, *, thinking_level: Optional[str] = None, task_key: Optional[str] = None):
        """Execute the prompt using ChatCore."""
        if not self.chat_core:
            self.log("Error: No ChatCore instance set")
            return
        
        # If needs approval and not yet approved, store prompt and wait
        if self.needs_approval and not self._is_approved:
            self._pending_prompt = prompt
            self._pending_thinking_level = thinking_level
            self._pending_task_key = task_key
            self.log("Waiting for approval to start...")
            return
        
        model = self.chat_core.get_current_model()
        provider = self.chat_core.get_current_provider()
        
        if not model or not provider:
            self.log("Error: No model selected")
            return
        
        self._thinking_level = thinking_level
        self._task_key = task_key

        self.log(f"Model: {model} @ {provider}")
        if thinking_level:
            self.log(f"Thinking: {thinking_level}")
        self.log(f"Prompt length: {len(prompt)} characters")
        self.log("-" * 40)
        
        self.stop_button.setEnabled(True)
        self._response_text = ""
        
        # Start worker
        self._worker = LLMWorker(self.chat_core, prompt, thinking_level=thinking_level, task_key=task_key)
        self._worker.chunk_received.connect(self._on_chunk)
        self._worker.response_complete.connect(self._on_complete)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.log_message.connect(self.log)
        self._worker.start()
    
    def _on_approve(self):
        """Handle approval button click."""
        self._is_approved = True
        if self.approve_button:
            self.approve_button.setEnabled(False)
            self.approve_button.setText("✓ Approved")
        
        self.gate_approved.emit()
        
        # Execute pending prompt if exists
        if self._pending_prompt:
            self.execute_prompt(
                self._pending_prompt,
                thinking_level=self._pending_thinking_level,
                task_key=self._pending_task_key
            )
            self._pending_prompt = None
    
    def _on_chunk(self, chunk: str):
        """Handle incoming chunk."""
        self._response_text += chunk
        cursor = self.response_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(chunk)
        self.response_display.setTextCursor(cursor)
        self.response_display.verticalScrollBar().setValue(
            self.response_display.verticalScrollBar().maximum()
        )
    
    def _on_complete(self, response: str):
        """Handle completion."""
        self.stop_button.setEnabled(False)
        self.log("-" * 40)
        self.log("Task completed successfully!")
        self.task_completed.emit(True, response)
    
    def _on_error(self, error: str):
        """Handle error."""
        self.stop_button.setEnabled(False)
        self.log(f"Error: {error}")
        self.response_display.setPlainText(f"Error: {error}")
        self.response_display.setStyleSheet(
            self.response_display.styleSheet() + "color: #ff6b6b;"
        )
        self.task_completed.emit(False, error)
    
    def _on_stop(self):
        """Handle stop button."""
        if self._worker:
            self._worker.request_stop()
            self._worker.wait(1000)
            self.stop_button.setEnabled(False)
            self.log("Task stopped by user")
    
    def closeEvent(self, event):
        """Handle window close."""
        if self._worker and self._worker.isRunning():
            self._worker.request_stop()
            self._worker.wait(1000)
        super().closeEvent(event)
