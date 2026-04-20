"""
Sentence Aligner Tab - Experimental module for visually aligning sentence start points
via audio envelope inspection and AI vision models.

Layout:
- Top: Drag-and-drop zone for media files or result directories
- Bottom (horizontal splitter):
  - Left: Table of bilingual sentence-axis candidates
  - Right (vertical splitter):
    - Upper: Waveform drawing zone (ruler + amplitude + subtitle track)
    - Lower: Model selector + options + Send button
"""

from pathlib import Path

import numpy as np
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QFrame, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QLabel, QPushButton, QSizePolicy,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont

from .tab_interface import TabInterface
from .styles.style_manager import get_drop_zone_stylesheet
from .components.model_selector import ModelSelectorWidget
from .components.waveform_drawing_zone import WaveformDrawingZone
from .flying_message import show_flying_message
from .util.add_zero_wide_char_to_str import add_zero_wide_char_to_str
from src.configuration_manager.configuration_manager import ConfigManager
from src.util.filename_sanitizer import FilenameSanitizer
from src.sentence_aligner.audio_extractor import extract_amplitude_bins
from src.sentence_aligner.alignment_loader import load_aligned_rows


# Padding (seconds) added before/after the selected subtitle for context
VIEW_PADDING_SEC = 1.0


def _strip_time_token_braces(raw_token: str) -> str:
    token = raw_token.strip()
    if token.startswith("{"):
        token = token[1:]
    if token.endswith("}"):
        token = token[:-1]
    return token.strip()


def _format_hover_time(seconds: float) -> str:
    if seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds - minutes * 60
        return f"{minutes:02}:{secs:05.2f}"

    hours = int(seconds // 3600)
    remaining = seconds - hours * 3600
    minutes = int(remaining // 60)
    secs = remaining - minutes * 60
    return f"{hours}:{minutes:02}:{secs:05.2f}"


def _format_time_cell(record) -> tuple[str, str]:
    if record is None:
        return "", ""

    display_tokens = [
        _strip_time_token_braces(token)
        for token in (record.raw_start_token, record.raw_end_token)
        if token
    ]
    display_text = " -> ".join(display_tokens)

    tooltip_tokens = []
    if record.start_sec is not None:
        tooltip_tokens.append(_format_hover_time(record.start_sec))
    if record.end_sec is not None:
        tooltip_tokens.append(_format_hover_time(record.end_sec))
    tooltip_text = " -> ".join(tooltip_tokens)

    return display_text, tooltip_text


# --------------------------------------------------------- Worker thread --

class _WaveformThread(QThread):
    """Runs ffmpeg + numpy amplitude extraction off the main thread."""
    result_ready = pyqtSignal(object)  # np.ndarray
    error = pyqtSignal(str)

    def __init__(self, media_path: str, start_sec: float, duration_sec: float, num_bins: int):
        super().__init__()
        self._media_path = media_path
        self._start_sec = start_sec
        self._duration_sec = duration_sec
        self._num_bins = num_bins

    def run(self):
        try:
            amps = extract_amplitude_bins(
                self._media_path,
                self._start_sec,
                self._duration_sec,
                num_bins=self._num_bins,
            )
            self.result_ready.emit(amps)
        except Exception as exc:
            self.error.emit(str(exc))


# --------------------------------------------------------- Main tab ------

class SentenceAlignerTab(TabInterface):
    """Experimental tab for AI-assisted sentence boundary alignment."""

    def __init__(self):
        super().__init__("Sentence Aligner")
        self.current_file_path = ""
        self.pending_directory = ""
        self.result_directory = ""
        self.aligned_rows = []

        self._worker_thread: QThread | None = None
        self._pending_row: int = -1

        config_manager = ConfigManager()
        paths = config_manager.get_paths_config()
        result_dir = Path(paths.get('result_dir', './transcription_result'))
        self.filename_sanitizer = FilenameSanitizer(result_dir)
        self._result_dir_base = result_dir

        self.init_ui()
        self.setAcceptDrops(True)

    # ------------------------------------------------------------------ UI --
    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        # -- top: drop zone --
        self.drop_label = QLabel("Drag a media file or result directory here, or load via Time Slicer")
        self.drop_label.setProperty("dropZone", True)
        self.drop_label.setAlignment(Qt.AlignCenter)
        self.drop_label.setFixedHeight(96)
        root_layout.addWidget(self.drop_label)

        # -- bottom: horizontal splitter --
        self.h_splitter = QSplitter(Qt.Horizontal)

        # left: subtitle table
        self._build_subtitle_table()
        self.h_splitter.addWidget(self.subtitle_table)

        # right: vertical splitter (drawing zone + controls)
        self.v_splitter = QSplitter(Qt.Vertical)

        self.waveform_widget = WaveformDrawingZone()
        self.v_splitter.addWidget(self.waveform_widget)

        self._build_control_panel()
        self.v_splitter.addWidget(self.control_panel)

        self.v_splitter.setStretchFactor(0, 3)
        self.v_splitter.setStretchFactor(1, 1)

        self.h_splitter.addWidget(self.v_splitter)
        self.h_splitter.setSizes([480, 480])

        root_layout.addWidget(self.h_splitter, stretch=1)

        self.setStyleSheet(get_drop_zone_stylesheet() + self._local_stylesheet())

    def _build_subtitle_table(self):
        self.subtitle_table = QTableWidget(0, 4)
        self.subtitle_table.setHorizontalHeaderLabels(
            ["Time (Original)", "Original", "Time (Translation)", "Translation"]
        )
        self.subtitle_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.subtitle_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.subtitle_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.subtitle_table.verticalHeader().setVisible(True)
        self.subtitle_table.setWordWrap(False)
        self.subtitle_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)

        header = self.subtitle_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setStretchLastSection(True)

        self.subtitle_table.currentCellChanged.connect(self._on_current_cell_changed)

    def _build_control_panel(self):
        self.control_panel = QFrame()
        self.control_panel.setObjectName("controlPanel")
        self.control_panel.setFrameShape(QFrame.StyledPanel)
        layout = QVBoxLayout(self.control_panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        model_row = QHBoxLayout()
        model_label = QLabel("Model:")
        model_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        model_row.addWidget(model_label)

        self.model_selector = ModelSelectorWidget(applicable_task="image-analysis")
        model_row.addWidget(self.model_selector)
        model_row.addStretch()
        layout.addLayout(model_row)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.send_button = QPushButton("Send")
        self.send_button.setEnabled(False)
        self.send_button.setFixedWidth(100)
        btn_row.addWidget(self.send_button)
        layout.addLayout(btn_row)

    # ---------------------------------------------------------- Stylesheet --
    @staticmethod
    def _local_stylesheet():
        return """
            QFrame#controlPanel {
                background-color: #f5f5f5;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
            }
            QTableWidget {
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
                font-size: 13px;
                gridline-color: #e0e0e0;
            }
            QHeaderView::section {
                background-color: #e8e8e8;
                padding: 4px 6px;
                border: none;
                border-right: 1px solid #d0d0d0;
                border-bottom: 1px solid #d0d0d0;
                font-weight: bold;
                font-size: 12px;
            }
        """

    # --------------------------------------------------- Drag-and-drop ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            self.drop_label.setProperty("dragOver", True)
            self.drop_label.style().unpolish(self.drop_label)
            self.drop_label.style().polish(self.drop_label)
            self.drop_label.setText("Drop to load file")
            event.accept()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.drop_label.setProperty("dragOver", False)
        self.drop_label.style().unpolish(self.drop_label)
        self.drop_label.style().polish(self.drop_label)
        self.drop_label.setText("Drag a media file or result directory here, or load via Time Slicer")
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.drop_label.setProperty("dragOver", False)
        self.drop_label.style().unpolish(self.drop_label)
        self.drop_label.style().polish(self.drop_label)
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            dropped_path = Path(files[0])
            if dropped_path.is_dir():
                self.pending_directory = str(dropped_path)
                self.drop_label.setText(f"Loaded directory: {add_zero_wide_char_to_str(str(dropped_path))}")
                self._try_load_axis_files()
                return

            parent_dir = dropped_path.parent
            if self._axis_files_exist(parent_dir):
                self.pending_directory = str(parent_dir)
                self.drop_label.setText(f"Loaded directory: {add_zero_wide_char_to_str(str(parent_dir))}")
                self._try_load_axis_files()
                return

            self.current_file_path = str(dropped_path)
            display = add_zero_wide_char_to_str(self.current_file_path)
            self.drop_label.setText(f"Loaded media: {display}")
            self._derive_and_load(self.current_file_path)

    # --------------------------------------------------- Broadcast -------
    def update_from_other_tab(self, data):
        """Receive broadcast from Time Slicer via MainWindow."""
        file_path = data.get("file_path")
        if not file_path:
            return
        self.current_file_path = file_path
        display = add_zero_wide_char_to_str(file_path)
        self.drop_label.setText(f"Loaded media: {display}")
        self._derive_and_load(file_path)

    # --------------------------------------------------- Derive dir ------
    def _derive_and_load(self, file_path: str):
        """Resolve the transcription result directory and load sentence-axis files."""
        resolved_dir = self._resolve_axis_directory(file_path)
        self.pending_directory = str(resolved_dir) if resolved_dir is not None else ""
        self._try_load_axis_files()

    def _resolve_axis_directory(self, file_path: str) -> Path | None:
        candidate_dirs: list[Path] = []

        asr_dir = self._get_asr_target_directory()
        if asr_dir is not None:
            candidate_dirs.append(asr_dir)

        if file_path:
            input_path = Path(file_path)
            safe_stem = self.filename_sanitizer.sanitize(input_path.stem)
            derived_dir = self._result_dir_base / safe_stem
            if derived_dir not in candidate_dirs:
                candidate_dirs.append(derived_dir)

        for candidate in candidate_dirs:
            if self._axis_files_exist(candidate):
                return candidate

        return candidate_dirs[0] if candidate_dirs else None

    def _get_asr_target_directory(self) -> Path | None:
        main_window = self.window()
        asr_tab = getattr(main_window, "asr_postprocess_tab", None)
        target_directory = getattr(asr_tab, "target_directory", "")
        if not target_directory:
            return None

        target_path = Path(target_directory)
        if target_path.exists():
            return target_path
        return None

    @staticmethod
    def _axis_files_exist(directory: Path) -> bool:
        return (
            directory / "句轴原文.txt"
        ).exists() and (
            directory / "句轴译文.txt"
        ).exists()

    def _clear_preview(self):
        self._cancel_worker()
        self._pending_row = -1
        self.waveform_widget.clear()

    def _clear_table(self):
        self.aligned_rows = []
        self.subtitle_table.clearContents()
        self.subtitle_table.setRowCount(0)

    def _try_load_axis_files(self):
        if not self.pending_directory:
            self._clear_table()
            self._clear_preview()
            return

        result_dir = Path(self.pending_directory)
        orig_path = result_dir / "句轴原文.txt"
        trans_path = result_dir / "句轴译文.txt"

        if orig_path.exists() and trans_path.exists():
            self.result_directory = self.pending_directory
            self._clear_preview()
            rows = load_aligned_rows(orig_path, trans_path)
            self.aligned_rows = rows
            self._populate_table(rows)
            show_flying_message(self, f"Loaded {len(rows)} aligned rows")
            return

        self.result_directory = ""
        self._clear_table()
        self._clear_preview()
        show_flying_message(self, f"句轴原文.txt / 句轴译文.txt not found in {self.pending_directory}")

    def showEvent(self, event):
        super().showEvent(event)
        if not self.result_directory and self.pending_directory:
            self._try_load_axis_files()

    # --------------------------------------------------- Table population --
    def _populate_table(self, entries: list):
        self.subtitle_table.clearContents()
        self.subtitle_table.setRowCount(len(entries))
        mono_font = QFont("Consolas", 11)

        for row, e in enumerate(entries):
            self.subtitle_table.setVerticalHeaderItem(row, QTableWidgetItem(str(row + 1)))

            orig_time_text, orig_time_tooltip = _format_time_cell(e.orig_record)
            orig_time_item = QTableWidgetItem(orig_time_text)
            orig_time_item.setFont(mono_font)
            if orig_time_tooltip:
                orig_time_item.setToolTip(orig_time_tooltip)
            self.subtitle_table.setItem(row, 0, orig_time_item)

            orig_text = e.orig_record.text if e.orig_record is not None else ""
            orig_item = QTableWidgetItem(orig_text)
            self.subtitle_table.setItem(row, 1, orig_item)

            trans_time_text, trans_time_tooltip = _format_time_cell(e.trans_record)
            trans_time_item = QTableWidgetItem(trans_time_text)
            trans_time_item.setFont(mono_font)
            if trans_time_tooltip:
                trans_time_item.setToolTip(trans_time_tooltip)
            self.subtitle_table.setItem(row, 2, trans_time_item)

            trans_text = e.trans_record.text if e.trans_record is not None else ""
            trans_item = QTableWidgetItem(trans_text)
            self.subtitle_table.setItem(row, 3, trans_item)

        self._resize_columns()

    def _resize_columns(self):
        """Fit time columns, then split the remaining width across text columns."""
        self.subtitle_table.resizeColumnToContents(0)
        self.subtitle_table.resizeColumnToContents(2)
        time_w = self.subtitle_table.columnWidth(0) + self.subtitle_table.columnWidth(2)
        total = self.subtitle_table.viewport().width()
        remaining = max(total - time_w, 240)
        self.subtitle_table.setColumnWidth(1, int(remaining * 0.5))
        self.subtitle_table.setColumnWidth(3, int(remaining * 0.5))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.subtitle_table.rowCount() > 0:
            self._resize_columns()

    # --------------------------------------------------- Row selection ------
    def _on_current_cell_changed(self, current_row, _current_col, _prev_row, _prev_col):
        """Triggered by both keyboard navigation and mouse row changes."""
        self._refresh_drawing_zone(current_row)

    # ------------------------------------------------ Waveform loading ----
    def _refresh_drawing_zone(self, row: int):
        """Dispatch waveform extraction to a background thread for the selected row."""
        if row < 0 or row >= len(self.aligned_rows):
            return

        aligned_row = self.aligned_rows[row]
        if (
            not aligned_row.previewable
            or aligned_row.preview_start_sec is None
            or aligned_row.preview_end_sec is None
        ):
            self._clear_preview()
            show_flying_message(self, "Selected row has no safe timeline preview")
            return

        if not self.current_file_path or not Path(self.current_file_path).exists():
            self._clear_preview()
            show_flying_message(self, "Waveform preview needs a loaded media file")
            return

        self._cancel_worker()

        self._pending_row = row
        preview_start = aligned_row.preview_start_sec
        preview_end = aligned_row.preview_end_sec

        view_start = max(preview_start - VIEW_PADDING_SEC, 0.0)
        view_end = preview_end + VIEW_PADDING_SEC
        view_duration = view_end - view_start

        draw_w = max(self.waveform_widget.width() - 100, 200)
        num_bins = min(draw_w, 1200)

        thread = _WaveformThread(self.current_file_path, view_start, view_duration, num_bins)
        thread.result_ready.connect(lambda amps, r=row: self._on_waveform_ready(amps, r))
        thread.error.connect(self._on_waveform_error)
        thread.finished.connect(lambda t=thread: self._on_worker_finished(t))
        thread.finished.connect(thread.deleteLater)

        self._worker_thread = thread
        thread.start()

    def _on_worker_finished(self, finished_thread: QThread):
        if self._worker_thread is finished_thread:
            self._worker_thread = None

    def _cancel_worker(self):
        if self._worker_thread is not None:
            thread = self._worker_thread
            thread.quit()
            thread.wait(500)
            self._worker_thread = None

    def _on_waveform_ready(self, amplitudes: np.ndarray, row: int):
        """Callback on main thread when amplitude data is ready."""
        if row != self._pending_row:
            return
        if row < 0 or row >= len(self.aligned_rows):
            return

        aligned_row = self.aligned_rows[row]
        if (
            not aligned_row.previewable
            or aligned_row.preview_start_sec is None
            or aligned_row.preview_end_sec is None
        ):
            self._clear_preview()
            return

        view_start = max(aligned_row.preview_start_sec - VIEW_PADDING_SEC, 0.0)
        view_end = aligned_row.preview_end_sec + VIEW_PADDING_SEC
        view_duration = view_end - view_start

        self.waveform_widget.set_data(
            amplitudes=amplitudes,
            start_sec=view_start,
            duration_sec=view_duration,
            subtitle_text=aligned_row.preview_text,
            sub_start_sec=aligned_row.preview_start_sec,
            sub_end_sec=aligned_row.preview_end_sec,
        )

    def _on_waveform_error(self, error_msg: str):
        show_flying_message(self, f"Waveform error: {error_msg}")
        self.waveform_widget.clear()
