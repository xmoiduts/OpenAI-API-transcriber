"""
Task Popup Window - Window for displaying LLM task execution progress and results.

Features:
- Embeddable TaskExecutionPanel (shared by single-task popup and assemble group)
- Painted per-line length gutter aligned to QTextBlock geometry
- Concurrent-safe LLMWorker (no process-wide stdout/stderr redirect)
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextBrowser, QPlainTextEdit, QWidget, QApplication,
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QTextCursor, QPainter, QColor, QFontMetrics
from typing import Optional
import sys
from pathlib import Path

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

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(8, 8, 8, 8)
        self.content.hide()
        layout.addWidget(self.content)

        self._title = title

    def _toggle(self):
        self._is_collapsed = not self._is_collapsed
        self.content.setVisible(not self._is_collapsed)
        arrow = "▶" if self._is_collapsed else "▼"
        self.toggle_btn.setText(f"{arrow} {self._title}")

    def add_widget(self, widget: QWidget):
        self.content_layout.addWidget(widget)

    def set_expanded(self, expanded: bool):
        if expanded != (not self._is_collapsed):
            self._toggle()


class LengthGutter(QWidget):
    """Painted length gutter aligned to a QPlainTextEdit's block geometry."""

    GUTTER_WIDTH = 52

    def __init__(self, editor: QPlainTextEdit, parent: Optional[QWidget] = None):
        super().__init__(parent)
        from util.text_metrics import calc_length, extract_body_text
        self._calc_length = calc_length
        self._extract_body = extract_body_text
        self._editor = editor
        self.setFixedWidth(self.GUTTER_WIDTH)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        editor.verticalScrollBar().valueChanged.connect(self.update)
        editor.document().documentLayout().documentSizeChanged.connect(self.update)
        editor.cursorPositionChanged.connect(self.update)
        editor.textChanged.connect(self.update)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(event.rect(), QColor("#f8f8f8"))
        painter.setPen(QColor("#e0e0e0"))
        painter.drawLine(0, 0, 0, self.height())

        font = self._editor.font()
        painter.setFont(font)
        painter.setPen(QColor("#999999"))
        metrics = QFontMetrics(font)
        line_h = metrics.lineSpacing()

        block = self._editor.document().begin()
        offset = self._editor.contentOffset()
        viewport_h = self._editor.viewport().height()

        while block.isValid():
            geom = self._editor.blockBoundingGeometry(block).translated(offset)
            y = int(geom.top())
            if y > viewport_h:
                break
            if y + int(geom.height()) >= 0 and block.isVisible():
                body = self._extract_body(block.text())
                length = self._calc_length(body)
                painter.drawText(
                    0,
                    y,
                    self.width() - 4,
                    line_h,
                    Qt.AlignRight | Qt.AlignVCenter,
                    f"{length:g}",
                )
            block = block.next()


class ResponseWithLengthPanel(QWidget):
    """Response editor with a painted per-line length gutter."""

    MONO_FONT = "Consolas, Monaco, 'Courier New', monospace"
    FONT_SIZE_PX = 11

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        from util.text_metrics import calc_length, extract_body_text
        self._calc_length = calc_length
        self._extract_body = extract_body_text

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.response_display = QPlainTextEdit()
        self.response_display.setObjectName("responseDisplay")
        self.response_display.setReadOnly(True)
        self.response_display.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.response_display.setMinimumHeight(150)
        self.response_display.setFont(QFont("Consolas", 11))

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

        self.length_gutter = LengthGutter(self.response_display)
        self.length_gutter.setStyleSheet(
            "background-color: #f8f8f8; border: 1px solid #e0e0e0; border-left: none;"
        )

        layout.addWidget(self.response_display, 1)
        layout.addWidget(self.length_gutter, 0)

        # Keep gutter height in sync with editor viewport
        self.response_display.verticalScrollBar().valueChanged.connect(
            self.length_gutter.update
        )
        self.response_display.document().documentLayout().documentSizeChanged.connect(
            self.length_gutter.update
        )

    def append_chunk(self, chunk: str):
        cursor = self.response_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(chunk)
        self.response_display.setTextCursor(cursor)
        self.response_display.verticalScrollBar().setValue(
            self.response_display.verticalScrollBar().maximum()
        )
        self.length_gutter.update()

    def get_plain_text(self) -> str:
        return self.response_display.toPlainText()

    def set_plain_text(self, text: str):
        self.response_display.setPlainText(text)
        self.length_gutter.update()

    def get_line_lengths(self) -> list:
        result = []
        text = self.response_display.toPlainText()
        for idx, raw_line in enumerate(text.split("\n")):
            body = self._extract_body(raw_line)
            result.append((idx, self._calc_length(body)))
        return result


class LLMWorker(QThread):
    """Worker thread for LLM operations.

    Does NOT redirect process-wide stdout/stderr (unsafe under concurrency).
    Provider errors are reported via ChatCore on_error callback + exceptions.
    """

    chunk_received = pyqtSignal(str)
    response_complete = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    log_message = pyqtSignal(str)

    def __init__(
        self,
        chat_core: ChatCore,
        prompt: str,
        thinking_level: Optional[str] = None,
        task_key: Optional[str] = None,
    ):
        super().__init__()
        self.chat_core = chat_core
        self.prompt = prompt
        self.thinking_level = thinking_level
        self.task_key = task_key
        self._stop_requested = False
        self._error_message: Optional[str] = None

    def run(self):
        try:
            self.log_message.emit("Starting LLM request...")
            full_response = ""
            self._error_message = None

            # Capture ChatCore/provider errors without stdout hijacking.
            def _on_error(exc: Exception):
                self._error_message = str(exc)
                self.log_message.emit(f"[ChatCore] {exc}")

            try:
                self.chat_core.set_callbacks(on_error=_on_error)
            except Exception:
                pass

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

            if self._stop_requested:
                return

            if self._error_message and not full_response:
                self.error_occurred.emit(self._error_message)
                return

            if self._error_message and full_response:
                # Partial output kept; still report as error completion upstream.
                self.log_message.emit(f"Stream ended with error: {self._error_message}")
                self.error_occurred.emit(self._error_message)
                return

            self.log_message.emit("Response complete.")
            self.response_complete.emit(full_response)

        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            try:
                self.chat_core.set_callbacks(
                    on_response_start=None,
                    on_response_chunk=None,
                    on_response_complete=None,
                    on_error=None,
                )
            except Exception:
                pass

    def request_stop(self):
        self._stop_requested = True


class TaskExecutionPanel(QWidget):
    """Embeddable task execution UI (context / log / response / controls).

    Used both inside TaskPopupWindow and AssembleTaskGroupWindow cards.
    """

    task_completed = pyqtSignal(bool, str)  # success, response
    gate_approved = pyqtSignal()
    stream_activity = pyqtSignal(str)
    auto_quenched = pyqtSignal()
    stopped = pyqtSignal()  # user/auto stop without completion

    def __init__(
        self,
        task_name: str = "Task",
        line_range: Optional[tuple] = None,
        parent: Optional[QWidget] = None,
        needs_approval: bool = False,
        slice_info: Optional[str] = None,
        enable_line_metrics: bool = False,
        max_line_length: float = 50.0,
        max_over_limit_pct: float = 12.5,
        show_close_button: bool = True,
        copy_button_label: str = "Copy Output",
        compact_header: bool = False,
    ):
        super().__init__(parent)
        self.task_name = task_name
        self.line_range = line_range
        self.needs_approval = needs_approval
        self.slice_info = slice_info
        self.enable_line_metrics = enable_line_metrics
        self._max_line_length = max_line_length
        self._max_over_limit_pct = max_over_limit_pct
        self._show_close_button = show_close_button
        self._copy_button_label = copy_button_label
        self._compact_header = compact_header

        self.chat_core: Optional[ChatCore] = None
        self._worker: Optional[LLMWorker] = None
        self._response_text = ""
        self._thinking_level: Optional[str] = None
        self._task_key: Optional[str] = None
        self._is_approved = not needs_approval
        self._pending_prompt = None
        self._pending_thinking_level = None
        self._pending_task_key = None

        self._line_mappings: Optional[dict] = None
        self._conversion_buffer = ""
        self._converted_text = ""
        self._current_offset = 0

        self._response_panel: Optional[ResponseWithLengthPanel] = None
        self._status = "idle"  # idle|waiting|running|success|error|interrupted

        self._init_ui()
        self._apply_styles()

    # ------------------------------------------------------------------ UI

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8 if self._compact_header else 16, 8, 8, 8)
        layout.setSpacing(8)

        header_text = self.task_name
        if self.line_range:
            header_text += f" (lines {self.line_range[0]}-{self.line_range[1]})"
        if self.slice_info:
            header_text += f" — {self.slice_info}"

        self.header_label = QLabel(header_text)
        self.header_label.setObjectName("popupHeader")
        header_font = QFont()
        header_font.setPointSize(11 if self._compact_header else 14)
        header_font.setBold(True)
        self.header_label.setFont(header_font)
        layout.addWidget(self.header_label)

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
        self.context_display.setMinimumHeight(60)
        self.context_display.setMaximumHeight(160)
        self.context_section.add_widget(self.context_display)
        layout.addWidget(self.context_section)

        log_label = QLabel("Console Log:")
        log_label.setStyleSheet("font-weight: bold; color: #555555;")
        layout.addWidget(log_label)

        self.log_display = QTextBrowser()
        self.log_display.setObjectName("logDisplay")
        self.log_display.setMinimumHeight(80)
        self.log_display.setMaximumHeight(140)
        layout.addWidget(self.log_display)

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
            self.response_display.setMinimumHeight(120)
            layout.addWidget(self.response_display, 1)

        self.converted_label = QLabel("Converted Output (Timestamps Restored):")
        self.converted_label.setStyleSheet("font-weight: bold; color: #555555;")
        self.converted_label.setVisible(False)
        layout.addWidget(self.converted_label)

        self.converted_display = QTextBrowser()
        self.converted_display.setObjectName("convertedDisplay")
        self.converted_display.setMinimumHeight(100)
        self.converted_display.setVisible(False)
        layout.addWidget(self.converted_display, 1)

        button_layout = QHBoxLayout()

        if self.needs_approval:
            self.approve_button = QPushButton("▶ Approve & Start")
            self.approve_button.setObjectName("approveButton")
            self.approve_button.clicked.connect(self._on_approve)
            button_layout.addWidget(self.approve_button)
        else:
            self.approve_button = None

        button_layout.addStretch()

        self.copy_button = QPushButton(self._copy_button_label)
        self.copy_button.setObjectName("copyButton")
        self.copy_button.clicked.connect(self._on_copy_output)
        button_layout.addWidget(self.copy_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setObjectName("stopButton")
        # clicked(bool) must not bind to emit_stopped — use a zero-arg lambda.
        self.stop_button.clicked.connect(lambda _checked=False: self._on_stop())
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.stop_button)

        if self._show_close_button:
            self.close_button = QPushButton("Close")
            self.close_button.setObjectName("closeButton")
            button_layout.addWidget(self.close_button)
        else:
            self.close_button = None

        layout.addLayout(button_layout)

    def _apply_styles(self):
        self.setStyleSheet("""
            QLabel#popupHeader {
                color: #333333;
                padding-bottom: 6px;
                border-bottom: 2px solid #4CAF50;
            }
            QTextBrowser#contextDisplay, QTextBrowser#logDisplay,
            QTextBrowser#responseDisplay, QTextBrowser#convertedDisplay {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #d0d0d0;
                border-radius: 6px;
                padding: 8px;
                font-family: Consolas, Monaco, "Courier New", monospace;
                font-size: 11px;
                selection-background-color: #b3d9ff;
            }
            QPushButton#stopButton {
                background-color: #ff6b6b;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton#stopButton:hover { background-color: #ee5a5a; }
            QPushButton#stopButton:disabled { background-color: #cccccc; }
            QPushButton#closeButton {
                background-color: #666666;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton#closeButton:hover { background-color: #555555; }
            QPushButton#approveButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
            }
            QPushButton#approveButton:hover { background-color: #45a049; }
            QPushButton#copyButton {
                background-color: #e0e0e0;
                color: #333333;
                border: 1px solid #c0c0c0;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton#copyButton:hover { background-color: #d0d0d0; }
        """)

    # -------------------------------------------------------------- public API

    @property
    def status(self) -> str:
        return self._status

    def get_response_text(self) -> str:
        return self._response_text

    def set_response_text(self, text: str):
        """Replace visible + internal response text (e.g. after punctuation strip)."""
        self._response_text = text or ""
        if self._response_panel is not None:
            self._response_panel.set_plain_text(self._response_text)
        else:
            self.response_display.setPlainText(self._response_text)
        self._update_output_char_count()

    def is_running(self) -> bool:
        return bool(self._worker and self._worker.isRunning())

    def is_waiting_approval(self) -> bool:
        return self.needs_approval and not self._is_approved and self._pending_prompt is not None

    def set_context(self, context: str):
        self.context_display.setPlainText(context)
        char_count = len(context)
        self.input_char_count_label.setText(f"Input: {char_count:,} chars")
        self.input_token_count_label.setText(f"~{char_count // 4:,} tokens")

    def set_line_mapping(self, line_mapping: dict):
        self._line_mappings = line_mapping

    def log(self, message: str):
        cursor = self.log_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(message + "\n")
        self.log_display.setTextCursor(cursor)
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum()
        )

    def set_chat_core(self, chat_core: ChatCore):
        self.chat_core = chat_core

    def set_quench_thresholds(self, max_line_length: float, max_over_limit_pct: float):
        self._max_line_length = max_line_length
        self._max_over_limit_pct = max_over_limit_pct

    def clear_runtime_state(self):
        """Reset displays for a retry without destroying the widget."""
        self._stop_worker_quiet()
        self._response_text = ""
        self._conversion_buffer = ""
        self._converted_text = ""
        self._current_offset = 0
        self.log_display.clear()
        if self._response_panel is not None:
            self._response_panel.set_plain_text("")
        else:
            self.response_display.clear()
        self.converted_display.clear()
        self.converted_label.setVisible(False)
        self.converted_display.setVisible(False)
        self._update_output_char_count()
        self.stop_button.setEnabled(False)
        self._status = "idle"

    def execute_prompt(
        self,
        prompt: str,
        *,
        thinking_level: Optional[str] = None,
        task_key: Optional[str] = None,
        force: bool = False,
    ):
        if not self.chat_core:
            self.log("Error: No ChatCore instance set")
            return

        if self.needs_approval and not self._is_approved and not force:
            self._pending_prompt = prompt
            self._pending_thinking_level = thinking_level
            self._pending_task_key = task_key
            self._status = "waiting"
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
        if self._response_panel is not None:
            self._response_panel.set_plain_text("")
        else:
            self.response_display.clear()
        self._status = "running"

        self._worker = LLMWorker(
            self.chat_core, prompt, thinking_level=thinking_level, task_key=task_key
        )
        self._worker.chunk_received.connect(self._on_chunk)
        self._worker.response_complete.connect(self._on_complete)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.log_message.connect(self._on_worker_log)
        self._worker.start()

    def approve_and_start(self):
        """Public approve used by Approve All."""
        self._on_approve()

    def request_stop(self):
        self._on_stop()

    # -------------------------------------------------------------- internals

    def _stop_worker_quiet(self):
        if self._worker and self._worker.isRunning():
            self._worker.request_stop()
            self._worker.wait(1000)
        self._worker = None

    def _on_approve(self):
        self._is_approved = True
        if self.approve_button:
            self.approve_button.setEnabled(False)
            self.approve_button.setText("✓ Approved")
        self.gate_approved.emit()
        if self._pending_prompt:
            prompt = self._pending_prompt
            thinking = self._pending_thinking_level
            task_key = self._pending_task_key
            self._pending_prompt = None
            self.execute_prompt(prompt, thinking_level=thinking, task_key=task_key, force=True)

    def _on_chunk(self, chunk: str):
        self.stream_activity.emit("chunk")

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

        if self.enable_line_metrics and "\n" in chunk:
            self._check_auto_quench()

        if self._line_mappings:
            try:
                from sentence_builder.response_converter import (
                    convert_response_incremental_multiregion,
                )
                converted_chunk, self._conversion_buffer, self._current_offset = (
                    convert_response_incremental_multiregion(
                        chunk,
                        self._line_mappings,
                        self._conversion_buffer,
                        self._current_offset,
                    )
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
        self.log(message)
        self.stream_activity.emit("log")

    def _update_output_char_count(self):
        self.output_char_count_label.setText(
            f"Output: {len(self._response_text):,} chars"
        )

    def _on_copy_output(self):
        text = self._response_text
        if text:
            QApplication.clipboard().setText(text)
            self.log("Output copied to clipboard.")

    def _check_auto_quench(self):
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
            self._on_stop(emit_stopped=False)
            self._status = "interrupted"
            self.auto_quenched.emit()

    def _on_complete(self, response: str):
        self.stop_button.setEnabled(False)
        if response:
            self._response_text = response
            if self._response_panel is not None:
                # Keep streamed text; only sync if empty mismatch
                if self._response_panel.get_plain_text() != response:
                    self._response_panel.set_plain_text(response)
            else:
                self.response_display.setPlainText(response)
        self._update_output_char_count()
        self.log("-" * 40)
        self.log("Task completed successfully!")
        self._status = "success"
        self.task_completed.emit(True, self._response_text)

    def _on_error(self, error: str):
        self.stop_button.setEnabled(False)
        self.log(f"Error: {error}")
        # Keep any partial output already streamed.
        self._status = "error"
        self.task_completed.emit(False, self._response_text or error)

    def _on_stop(self, emit_stopped: bool = True):
        """Stop the worker. Always mark interrupted when a worker existed.

        Note: do not connect QPushButton.clicked directly to this method —
        clicked(bool) would bind the checked flag onto *emit_stopped*.
        """
        if self._worker:
            was_running = self._worker.isRunning()
            self._worker.request_stop()
            if was_running:
                self._worker.wait(1000)
            self.stop_button.setEnabled(False)
            self.log("Task stopped by user")
            self._status = "interrupted"
            if emit_stopped:
                self.stopped.emit()
        elif self._status == "running":
            # UI thought it was running but worker is already gone.
            self.stop_button.setEnabled(False)
            self._status = "interrupted"
            if emit_stopped:
                self.stopped.emit()


class TaskPopupWindow(QDialog):
    """Compatibility wrapper: single-task popup around TaskExecutionPanel."""

    task_completed = pyqtSignal(bool, str)
    gate_approved = pyqtSignal()
    stream_activity = pyqtSignal(str)
    auto_quenched = pyqtSignal()

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

        title = f"Task: {task_name}"
        if slice_info:
            title += f" - {slice_info}"
        self.setWindowTitle(title)
        self.setMinimumSize(600, 500)
        self.setModal(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.panel = TaskExecutionPanel(
            task_name=task_name,
            line_range=line_range,
            needs_approval=needs_approval,
            slice_info=slice_info,
            enable_line_metrics=enable_line_metrics,
            max_line_length=max_line_length,
            max_over_limit_pct=max_over_limit_pct,
            show_close_button=True,
        )
        layout.addWidget(self.panel)

        # Forward panel signals
        self.panel.task_completed.connect(self.task_completed.emit)
        self.panel.gate_approved.connect(self.gate_approved.emit)
        self.panel.stream_activity.connect(self.stream_activity.emit)
        self.panel.auto_quenched.connect(self.auto_quenched.emit)

        if self.panel.close_button is not None:
            self.panel.close_button.clicked.connect(self.close)

        # Compatibility attributes used by existing callers
        self.chat_core = None
        self.stop_button = self.panel.stop_button
        self.approve_button = self.panel.approve_button
        self.copy_button = self.panel.copy_button
        self.close_button = self.panel.close_button
        self.response_display = self.panel.response_display
        self.log_display = self.panel.log_display
        self.context_display = self.panel.context_display

        self.setStyleSheet("QDialog { background-color: #ffffff; }")

    def set_context(self, context: str):
        self.panel.set_context(context)

    def set_line_mapping(self, line_mapping: dict):
        self.panel.set_line_mapping(line_mapping)

    def log(self, message: str):
        self.panel.log(message)

    def set_chat_core(self, chat_core: ChatCore):
        self.chat_core = chat_core
        self.panel.set_chat_core(chat_core)

    def execute_prompt(
        self,
        prompt: str,
        *,
        thinking_level: Optional[str] = None,
        task_key: Optional[str] = None,
    ):
        self.panel.execute_prompt(
            prompt, thinking_level=thinking_level, task_key=task_key
        )

    def set_quench_thresholds(self, max_line_length: float, max_over_limit_pct: float):
        self.panel.set_quench_thresholds(max_line_length, max_over_limit_pct)

    def closeEvent(self, event):
        if self.panel.is_running():
            self.panel.request_stop()
        super().closeEvent(event)
