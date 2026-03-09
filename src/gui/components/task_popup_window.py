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
    QTextBrowser, QPlainTextEdit, QFrame, QSizePolicy, QWidget,
    QScrollArea, QApplication, QSplitter
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


class ResponseWithLengthPanel(QWidget):
    """Side-by-side panel: left = response text, right = per-line length gutter.

    The right gutter is kept in sync with the left editor's word-wrapped
    layout so that each logical line's length value aligns with the first
    visual row of that line in the left editor.
    """

    MONO_FONT = "Consolas, Monaco, 'Courier New', monospace"
    FONT_SIZE_PX = 11

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        from util.text_metrics import calc_length, extract_body_text
        self._calc_length = calc_length
        self._extract_body = extract_body_text

        self._syncing_scroll = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left: response editor (read-only, word-wrap on)
        self.response_display = QPlainTextEdit()
        self.response_display.setObjectName("responseDisplay")
        self.response_display.setReadOnly(True)
        self.response_display.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.response_display.setMinimumHeight(150)

        # Right: length gutter (read-only, no wrap, narrow)
        self.length_display = QPlainTextEdit()
        self.length_display.setObjectName("lengthGutter")
        self.length_display.setReadOnly(True)
        self.length_display.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.length_display.setFixedWidth(52)
        self.length_display.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.length_display.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        shared_font_css = (
            f"font-family: {self.MONO_FONT}; font-size: {self.FONT_SIZE_PX}px;"
        )
        base_style = (
            "background-color: #ffffff; color: #333333; "
            "border: 1px solid #d0d0d0; border-radius: 6px; padding: 8px; "
            "selection-background-color: #b3d9ff; "
            + shared_font_css
        )
        self.response_display.setStyleSheet(
            f"QPlainTextEdit#responseDisplay {{ {base_style} }}"
        )
        gutter_style = (
            "background-color: #f8f8f8; color: #999999; "
            "border: 1px solid #e0e0e0; border-radius: 0px; padding: 8px 4px; "
            + shared_font_css
        )
        self.length_display.setStyleSheet(
            f"QPlainTextEdit#lengthGutter {{ {gutter_style} }}"
        )

        layout.addWidget(self.response_display, 1)
        layout.addWidget(self.length_display, 0)

        # Scroll sync: left -> right
        self.response_display.verticalScrollBar().valueChanged.connect(
            self._sync_scroll_to_gutter
        )

        # Re-sync gutter when content layout changes (e.g. word-wrap)
        self.response_display.document().documentLayout().documentSizeChanged.connect(
            self._rebuild_gutter
        )

    # ---- public helpers used by TaskPopupWindow ----

    def append_chunk(self, chunk: str):
        """Append streaming text and keep auto-scroll."""
        cursor = self.response_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(chunk)
        self.response_display.setTextCursor(cursor)
        self.response_display.verticalScrollBar().setValue(
            self.response_display.verticalScrollBar().maximum()
        )
        if "\n" in chunk:
            self._rebuild_gutter()
        else:
            self._update_last_gutter_line()

    def get_plain_text(self) -> str:
        return self.response_display.toPlainText()

    def set_plain_text(self, text: str):
        self.response_display.setPlainText(text)

    def get_line_lengths(self) -> list:
        """Return list of (line_index, body_length) for all logical lines."""
        result = []
        text = self.response_display.toPlainText()
        for idx, raw_line in enumerate(text.split("\n")):
            body = self._extract_body(raw_line)
            result.append((idx, self._calc_length(body)))
        return result

    # ---- private ----

    def _sync_scroll_to_gutter(self, value: int):
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        self.length_display.verticalScrollBar().setValue(value)
        self._syncing_scroll = False

    def _rebuild_gutter(self):
        """Rebuild the right gutter so each length label aligns with its block."""
        doc = self.response_display.document()
        lines: list[str] = []
        block = doc.begin()
        while block.isValid():
            text = block.text()
            body = self._extract_body(text)
            length = self._calc_length(body)
            lines.append(f"{length:g}")
            visual = block.layout().lineCount() if block.layout() else 1
            for _ in range(max(0, visual - 1)):
                lines.append("")
            block = block.next()

        old = self.length_display.toPlainText()
        new_text = "\n".join(lines)
        if old != new_text:
            self.length_display.setPlainText(new_text)
            self._sync_scroll_to_gutter(
                self.response_display.verticalScrollBar().value()
            )

    def _update_last_gutter_line(self):
        """Fast-path: only recompute the very last line in the gutter."""
        text = self.response_display.toPlainText()
        if not text:
            return
        last_line = text.rsplit("\n", 1)[-1]
        body = self._extract_body(last_line)
        length = self._calc_length(body)
        length_str = f"{length:g}"

        gutter_text = self.length_display.toPlainText()
        gutter_lines = gutter_text.split("\n") if gutter_text else []
        if gutter_lines:
            gutter_lines[-1] = length_str
        else:
            gutter_lines = [length_str]
        new_text = "\n".join(gutter_lines)
        if gutter_text != new_text:
            self.length_display.setPlainText(new_text)
            self._sync_scroll_to_gutter(
                self.response_display.verticalScrollBar().value()
            )


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
    - Optional converted output (for merge overlaps task)
    """
    
    task_completed = pyqtSignal(bool, str)  # success, response
    gate_approved = pyqtSignal()  # Emitted when gate button is clicked
    stream_activity = pyqtSignal(str)  # Emitted on streaming/log activity
    
    auto_quenched = pyqtSignal()  # Emitted when auto-quench stops streaming

    def __init__(
        self,
        task_name: str,
        line_range: Optional[tuple] = None,
        parent: Optional[QWidget] = None,
        needs_approval: bool = False,
        slice_info: Optional[str] = None,
        enable_line_metrics: bool = False,
        max_line_length: float = 50.0,
        max_over_limit_pct: float = 12.5,
    ):
        super().__init__(parent)
        self.task_name = task_name
        self.line_range = line_range
        self.needs_approval = needs_approval
        self.slice_info = slice_info
        self.enable_line_metrics = enable_line_metrics
        self._max_line_length = max_line_length
        self._max_over_limit_pct = max_over_limit_pct

        self.chat_core: Optional[ChatCore] = None
        self._worker: Optional[LLMWorker] = None
        self._response_text = ""
        self._thinking_level: Optional[str] = None
        self._task_key: Optional[str] = None
        self._is_approved = not needs_approval  # Auto-approve if not needed
        self._pending_prompt = None
        self._pending_thinking_level = None
        self._pending_task_key = None

        # For merge overlaps: line number mapping and conversion
        self._line_mappings: Optional[dict] = None  # offset -> {line_num -> (start, end, word)}
        self._conversion_buffer = ""  # Buffer for incremental conversion
        self._converted_text = ""  # Accumulated converted output
        self._current_offset = 0  # Track current Time offset during streaming

        # Line-metrics panel (only created when enable_line_metrics is True)
        self._response_panel: Optional[ResponseWithLengthPanel] = None

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

        # -- Context section (collapsible) with input char count header --
        self.context_section = CollapsibleSection("Context Sent to LLM")

        ctx_header_layout = QHBoxLayout()
        ctx_header_layout.setContentsMargins(0, 0, 0, 2)
        self.input_char_count_label = QLabel("Input: 0 chars")
        self.input_char_count_label.setStyleSheet("color: #888888; font-size: 11px;")
        ctx_header_layout.addWidget(self.input_char_count_label)
        ctx_header_layout.addStretch()
        self.input_token_count_label = QLabel("~0 tokens")
        self.input_token_count_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        ctx_header_layout.addWidget(self.input_token_count_label)
        ctx_header_w = QWidget()
        ctx_header_w.setLayout(ctx_header_layout)
        self.context_section.add_widget(ctx_header_w)

        self.context_display = QTextBrowser()
        self.context_display.setObjectName("contextDisplay")
        self.context_display.setMinimumHeight(100)
        self.context_display.setMaximumHeight(200)
        self.context_section.add_widget(self.context_display)

        layout.addWidget(self.context_section)

        # -- Console log section --
        log_label = QLabel("Console Log:")
        log_label.setStyleSheet("font-weight: bold; color: #555555;")
        layout.addWidget(log_label)

        self.log_display = QTextBrowser()
        self.log_display.setObjectName("logDisplay")
        self.log_display.setMinimumHeight(150)
        layout.addWidget(self.log_display)

        # -- Response section with character count --
        response_header_layout = QHBoxLayout()
        response_label = QLabel("LLM Response:")
        response_label.setStyleSheet("font-weight: bold; color: #555555;")
        response_header_layout.addWidget(response_label)

        response_header_layout.addStretch()

        self.output_char_count_label = QLabel("Output: 0 chars")
        self.output_char_count_label.setStyleSheet("color: #888888; font-size: 11px;")
        response_header_layout.addWidget(self.output_char_count_label)

        layout.addLayout(response_header_layout)

        if self.enable_line_metrics:
            self._response_panel = ResponseWithLengthPanel()
            self.response_display = self._response_panel.response_display
            layout.addWidget(self._response_panel, 1)
        else:
            self.response_display = QTextBrowser()
            self.response_display.setObjectName("responseDisplay")
            self.response_display.setMinimumHeight(150)
            layout.addWidget(self.response_display, 1)

        # Converted output section (initially hidden, shown during streaming if enabled)
        self.converted_label = QLabel("Converted Output (Timestamps Restored):")
        self.converted_label.setStyleSheet("font-weight: bold; color: #555555;")
        self.converted_label.setVisible(False)
        layout.addWidget(self.converted_label)

        self.converted_display = QTextBrowser()
        self.converted_display.setObjectName("convertedDisplay")
        self.converted_display.setMinimumHeight(150)
        self.converted_display.setVisible(False)
        layout.addWidget(self.converted_display, 1)

        # -- Button row --
        button_layout = QHBoxLayout()

        if self.needs_approval:
            self.approve_button = QPushButton("▶ Approve & Start")
            self.approve_button.setObjectName("approveButton")
            self.approve_button.clicked.connect(self._on_approve)
            button_layout.addWidget(self.approve_button)
        else:
            self.approve_button = None

        button_layout.addStretch()

        # Copy output (only for assemble / line-metrics mode, but harmless for all)
        self.copy_button = QPushButton("Copy Output")
        self.copy_button.setObjectName("copyButton")
        self.copy_button.clicked.connect(self._on_copy_output)
        button_layout.addWidget(self.copy_button)

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
            QTextBrowser#contextDisplay, QTextBrowser#logDisplay, QTextBrowser#responseDisplay, QTextBrowser#convertedDisplay {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                padding: 8px;
                font-family: Consolas, Monaco, "Courier New", monospace;
                font-size: 11px;
                selection-background-color: #b3d9ff;
            }
            QTextBrowser#contextDisplay:focus, QTextBrowser#logDisplay:focus, QTextBrowser#responseDisplay:focus, QTextBrowser#convertedDisplay:focus {
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
            QPushButton#copyButton {
                background-color: #e0e0e0;
                color: #333333;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton#copyButton:hover {
                background-color: #d0d0d0;
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
        """Set the context text and update input char/token counters."""
        self.context_display.setPlainText(context)
        char_count = len(context)
        self.input_char_count_label.setText(f"Input: {char_count:,} chars")
        self.input_token_count_label.setText(f"~{char_count // 4:,} tokens")
    
    def set_line_mapping(self, line_mapping: dict):
        """
        Set line number mapping for response conversion (merge overlaps task).
        
        Args:
            line_mapping: Dict mapping offset -> {line_num -> (original_start, original_end, word)}
                         This supports multiple regions with different offsets but same line numbers.
        """
        self._line_mappings = line_mapping
        # Conversion will be enabled when streaming starts
    
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
        self._worker.log_message.connect(self._on_worker_log)
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
        self.stream_activity.emit("chunk")

        # Show converted output section on first chunk if line mapping is set
        if self._line_mappings and not self.converted_display.isVisible():
            self.converted_label.setVisible(True)
            self.converted_display.setVisible(True)

        self._response_text += chunk

        if self._response_panel is not None:
            self._response_panel.append_chunk(chunk)
        else:
            cursor = self.response_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertText(chunk)
            self.response_display.setTextCursor(cursor)
            self.response_display.verticalScrollBar().setValue(
                self.response_display.verticalScrollBar().maximum()
            )

        self._update_output_char_count()

        # Auto-quench check (only when line metrics are active)
        if self.enable_line_metrics and "\n" in chunk:
            self._check_auto_quench()

        # Convert and update converted output if line mapping is available
        if self._line_mappings:
            try:
                from sentence_builder.response_converter import convert_response_incremental_multiregion
                converted_chunk, self._conversion_buffer, self._current_offset = convert_response_incremental_multiregion(
                    chunk, self._line_mappings, self._conversion_buffer, self._current_offset
                )
                if converted_chunk:
                    self._converted_text += converted_chunk
                    cursor = self.converted_display.textCursor()
                    cursor.movePosition(QTextCursor.End)
                    cursor.insertText(converted_chunk)
                    self.converted_display.setTextCursor(cursor)
                    self.converted_display.verticalScrollBar().setValue(
                        self.converted_display.verticalScrollBar().maximum()
                    )
            except Exception as e:
                self.log(f"Warning: Conversion error: {e}")

    def _on_worker_log(self, message: str):
        """Handle worker log messages."""
        self.log(message)
        self.stream_activity.emit("log")
    
    def _update_output_char_count(self):
        """Update the output character count label."""
        char_count = len(self._response_text)
        self.output_char_count_label.setText(f"Output: {char_count:,} chars")

    def _on_copy_output(self):
        """Copy the response text to clipboard (without length gutter)."""
        text = self._response_text
        if text:
            QApplication.clipboard().setText(text)
            self.log("Output copied to clipboard.")

    def set_quench_thresholds(self, max_line_length: float, max_over_limit_pct: float):
        """Update auto-quench thresholds at runtime."""
        self._max_line_length = max_line_length
        self._max_over_limit_pct = max_over_limit_pct

    def _check_auto_quench(self):
        """Stop streaming if too many lines exceed the length threshold."""
        if self._response_panel is None:
            return
        lengths = self._response_panel.get_line_lengths()
        total = len(lengths)
        if total < 3:
            return
        over = sum(1 for _, ln in lengths if ln > self._max_line_length)
        pct = (over / total) * 100.0
        if pct > self._max_over_limit_pct:
            self.log(
                f"AUTO-QUENCH: {over}/{total} lines ({pct:.1f}%) exceed "
                f"max length {self._max_line_length}. Stopping."
            )
            self._on_stop()
            self.auto_quenched.emit()

    def _on_complete(self, response: str):
        """Handle completion."""
        self.stop_button.setEnabled(False)
        self._update_output_char_count()  # Final update
        self.log("-" * 40)
        self.log("Task completed successfully!")
        self.task_completed.emit(True, response)
    
    def _on_error(self, error: str):
        """Handle error."""
        self.stop_button.setEnabled(False)
        self.log(f"Error: {error}")
        if self._response_panel is not None:
            self._response_panel.set_plain_text(f"Error: {error}")
        else:
            self.response_display.setPlainText(f"Error: {error}")
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
