"""
Sentence Aligner Tab - Experimental module for visually aligning sentence start points
via audio envelope inspection and AI vision models.

Layout:
- Top: Drag-and-drop zone for media files (broadcasts from Time Slicer)
- Bottom (horizontal splitter):
  - Left: Table of bilingual subtitle candidates (from subtitles-bilang.srt)
  - Right (vertical splitter):
    - Upper: Waveform drawing zone (ruler + amplitude + subtitle track)
    - Lower: Model selector + options + Send button
"""

import re
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


# Padding (seconds) added before/after the selected subtitle for context
VIEW_PADDING_SEC = 1.0


def _srt_ts_to_sec(ts: str) -> float:
    """Convert SRT timestamp 'HH:MM:SS,mmm' to seconds."""
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


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
        self.subtitle_entries = []

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
        self.drop_label = QLabel("Drag a media file here, or load via Time Slicer")
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
        self.subtitle_table = QTableWidget(0, 3)
        self.subtitle_table.setHorizontalHeaderLabels(["Time", "Translation", "Original"])
        self.subtitle_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.subtitle_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.subtitle_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.subtitle_table.verticalHeader().setVisible(False)
        self.subtitle_table.setWordWrap(False)
        self.subtitle_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)

        header = self.subtitle_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setStretchLastSection(True)

        self.subtitle_table.cellClicked.connect(self._on_table_row_clicked)
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
        self.drop_label.setText("Drag a media file here, or load via Time Slicer")
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.drop_label.setProperty("dragOver", False)
        self.drop_label.style().unpolish(self.drop_label)
        self.drop_label.style().polish(self.drop_label)
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        if files:
            self.current_file_path = files[0]
            display = add_zero_wide_char_to_str(self.current_file_path)
            self.drop_label.setText(f"Loaded: {display}")
            self._derive_and_load(self.current_file_path)

    # --------------------------------------------------- Broadcast -------
    def update_from_other_tab(self, data):
        """Receive broadcast from Time Slicer via MainWindow."""
        file_path = data.get("file_path")
        if not file_path:
            return
        self.current_file_path = file_path
        display = add_zero_wide_char_to_str(file_path)
        self.drop_label.setText(f"Loaded: {display}")
        self._derive_and_load(file_path)

    # --------------------------------------------------- Derive dir ------
    def _derive_and_load(self, file_path: str):
        """Derive the transcription result directory and load subtitles-bilang.srt."""
        input_path = Path(file_path)
        safe_stem = self.filename_sanitizer.sanitize(input_path.stem)
        result_dir = self._result_dir_base / safe_stem
        self.pending_directory = str(result_dir)
        self._try_load_srt()

    def _try_load_srt(self):
        if not self.pending_directory:
            return
        srt_path = Path(self.pending_directory) / "subtitles-bilang.srt"
        if srt_path.exists():
            self.result_directory = self.pending_directory
            entries = self._parse_srt(srt_path)
            self.subtitle_entries = entries
            self._populate_table(entries)
            show_flying_message(self, f"Loaded {len(entries)} subtitle entries")
        else:
            self.subtitle_table.setRowCount(0)
            show_flying_message(self, f"subtitles-bilang.srt not found in {self.pending_directory}")

    def showEvent(self, event):
        super().showEvent(event)
        if not self.result_directory and self.pending_directory:
            self._try_load_srt()

    # --------------------------------------------------- SRT parser ------
    @staticmethod
    def _parse_srt(srt_path: Path) -> list:
        """Parse bilingual SRT into list of dicts with float timestamps."""
        text = srt_path.read_text(encoding="utf-8")
        blocks = re.split(r"\n\s*\n", text.strip())
        entries = []
        for block in blocks:
            lines = block.strip().splitlines()
            if len(lines) < 3:
                continue
            time_match = re.match(
                r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})",
                lines[1],
            )
            if not time_match:
                continue
            start_ts = time_match.group(1)
            end_ts = time_match.group(2)
            translated = lines[2] if len(lines) > 2 else ""
            original = lines[3] if len(lines) > 3 else ""
            entries.append({
                "index": lines[0].strip(),
                "start": start_ts,
                "end": end_ts,
                "start_sec": _srt_ts_to_sec(start_ts),
                "end_sec": _srt_ts_to_sec(end_ts),
                "translated": translated.strip(),
                "original": original.strip(),
            })
        return entries

    # --------------------------------------------------- Table population --
    def _populate_table(self, entries: list):
        self.subtitle_table.setRowCount(len(entries))
        mono_font = QFont("Consolas", 11)

        for row, e in enumerate(entries):
            time_item = QTableWidgetItem(e['start'])
            time_item.setFont(mono_font)
            self.subtitle_table.setItem(row, 0, time_item)

            trans_item = QTableWidgetItem(e["translated"])
            self.subtitle_table.setItem(row, 1, trans_item)

            orig_item = QTableWidgetItem(e["original"])
            self.subtitle_table.setItem(row, 2, orig_item)

        self._resize_columns()

    def _resize_columns(self):
        """Set column widths: time fits content, then translation 40% / original 60%."""
        self.subtitle_table.resizeColumnToContents(0)
        time_w = self.subtitle_table.columnWidth(0)
        total = self.subtitle_table.viewport().width()
        remaining = max(total - time_w, 200)
        self.subtitle_table.setColumnWidth(1, int(remaining * 0.4))
        self.subtitle_table.setColumnWidth(2, int(remaining * 0.6))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.subtitle_table.rowCount() > 0:
            self._resize_columns()

    # --------------------------------------------------- Row selection ------
    def _on_table_row_clicked(self, row, _col=None):
        self._refresh_drawing_zone(row)

    def _on_current_cell_changed(self, current_row, _current_col, _prev_row, _prev_col):
        """Triggered by keyboard up/down navigation."""
        self._refresh_drawing_zone(current_row)

    # ------------------------------------------------ Waveform loading ----
    def _refresh_drawing_zone(self, row: int):
        """Dispatch waveform extraction to a background thread for the selected row."""
        if row < 0 or row >= len(self.subtitle_entries):
            return
        if not self.current_file_path:
            return

        # Cancel any in-flight extraction
        self._cancel_worker()

        self._pending_row = row
        e = self.subtitle_entries[row]

        view_start = max(e["start_sec"] - VIEW_PADDING_SEC, 0.0)
        view_end = e["end_sec"] + VIEW_PADDING_SEC
        view_duration = view_end - view_start

        draw_w = max(self.waveform_widget.width() - 100, 200)
        num_bins = min(draw_w, 1200)

        thread = _WaveformThread(self.current_file_path, view_start, view_duration, num_bins)
        thread.result_ready.connect(lambda amps, r=row: self._on_waveform_ready(amps, r))
        thread.error.connect(self._on_waveform_error)
        thread.finished.connect(self._on_worker_finished)
        thread.finished.connect(thread.deleteLater)

        self._worker_thread = thread
        thread.start()

    def _on_worker_finished(self):
        self._worker_thread = None

    def _cancel_worker(self):
        if self._worker_thread is not None:
            self._worker_thread.quit()
            self._worker_thread.wait(500)
            self._worker_thread = None

    def _on_waveform_ready(self, amplitudes: np.ndarray, row: int):
        """Callback on main thread when amplitude data is ready."""
        if row != self._pending_row:
            return
        if row < 0 or row >= len(self.subtitle_entries):
            return

        e = self.subtitle_entries[row]
        view_start = max(e["start_sec"] - VIEW_PADDING_SEC, 0.0)
        view_end = e["end_sec"] + VIEW_PADDING_SEC
        view_duration = view_end - view_start

        self.waveform_widget.set_data(
            amplitudes=amplitudes,
            start_sec=view_start,
            duration_sec=view_duration,
            subtitle_text=e["original"],
            sub_start_sec=e["start_sec"],
            sub_end_sec=e["end_sec"],
        )

    def _on_waveform_error(self, error_msg: str):
        show_flying_message(self, f"Waveform error: {error_msg}")
        self.waveform_widget.clear()
