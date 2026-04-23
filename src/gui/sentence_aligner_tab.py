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
    QLabel, QPushButton, QSizePolicy, QScrollArea,
)
from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QFont

from .tab_interface import TabInterface
from .styles.style_manager import get_drop_zone_stylesheet
from .components.model_selector import ModelSelectorWidget
from .components.waveform_drawing_zone import (
    WaveformDrawingZone,
    SentenceEntry,
    WordEntry,
    PIXELS_PER_SECOND,
)
from .flying_message import show_flying_message
from .util.add_zero_wide_char_to_str import add_zero_wide_char_to_str
from src.configuration_manager.configuration_manager import ConfigManager
from src.util.filename_sanitizer import FilenameSanitizer
from src.sentence_aligner.audio_extractor import extract_amplitude_bins
from src.sentence_aligner.alignment_loader import load_aligned_rows
from src.sentence_aligner.word_timestamps_loader import (
    WordTimeline,
    load_word_timeline,
)


# Padding (seconds) added before/after the selected subtitle for context
VIEW_PADDING_SEC = 1.0

# Upper bound on how many amplitude bins we extract. Anything beyond ~12000
# bins is indistinguishable at the configured pixels-per-second and just
# wastes CPU in ffmpeg.
MAX_WAVEFORM_BINS = 12000

# Fallback duration for trans rects without a usable paired orig range.
_TRANS_FALLBACK_DURATION_SEC = 1.0

# When two trans rows in the viewport share this close a start time,
# only the first (in aligned_rows order) is rendered.
_SAME_START_EPSILON_SEC = 1e-6


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
        self.word_timeline: WordTimeline = WordTimeline()

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

        # -- persistent status line shown when axis files loaded but media is missing --
        self.media_status_label = QLabel("")
        self.media_status_label.setProperty("mediaStatus", False)
        self.media_status_label.setAlignment(Qt.AlignCenter)
        self.media_status_label.setVisible(False)
        root_layout.addWidget(self.media_status_label)

        # -- bottom: horizontal splitter --
        self.h_splitter = QSplitter(Qt.Horizontal)

        # left: subtitle table
        self._build_subtitle_table()
        self.h_splitter.addWidget(self.subtitle_table)

        # right: vertical splitter (drawing zone + controls)
        self.v_splitter = QSplitter(Qt.Vertical)

        self.waveform_widget = WaveformDrawingZone()
        self.waveform_scroll = QScrollArea()
        self.waveform_scroll.setWidget(self.waveform_widget)
        self.waveform_scroll.setWidgetResizable(False)
        self.waveform_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.waveform_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.waveform_scroll.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.v_splitter.addWidget(self.waveform_scroll)

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
            QLabel[mediaStatus="warn"] {
                color: #C0392B;
                background-color: #FDECEA;
                border: 1px solid #F5C6C0;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 12px;
                font-weight: bold;
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
        self._refresh_media_status()

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

    def _refresh_media_status(self) -> None:
        """Show/hide the red-light warning when axis files are loaded but media isn't."""
        need_warning = bool(self.pending_directory) and (
            not self.current_file_path or not Path(self.current_file_path).exists()
        )
        if need_warning:
            self.media_status_label.setText(
                "\U0001F534  media not yet loaded, load it in slicer tab"
            )
            self.media_status_label.setProperty("mediaStatus", "warn")
            self.media_status_label.setVisible(True)
        else:
            self.media_status_label.setText("")
            self.media_status_label.setProperty("mediaStatus", False)
            self.media_status_label.setVisible(False)
        self.media_status_label.style().unpolish(self.media_status_label)
        self.media_status_label.style().polish(self.media_status_label)

    def _clear_preview(self):
        self._cancel_worker()
        self._pending_row = -1
        self.waveform_widget.clear()

    def _clear_table(self):
        self.aligned_rows = []
        self.word_timeline = WordTimeline()
        self.subtitle_table.clearContents()
        self.subtitle_table.setRowCount(0)

    def _try_load_axis_files(self):
        if not self.pending_directory:
            self._clear_table()
            self._clear_preview()
            self._refresh_media_status()
            return

        result_dir = Path(self.pending_directory)
        orig_path = result_dir / "句轴原文.txt"
        trans_path = result_dir / "句轴译文.txt"

        if orig_path.exists() and trans_path.exists():
            self.result_directory = self.pending_directory
            self._clear_preview()
            rows = load_aligned_rows(orig_path, trans_path)
            self.aligned_rows = rows
            self._load_word_timeline(result_dir)
            self._populate_table(rows)
            show_flying_message(self, f"Loaded {len(rows)} aligned rows")
            self._refresh_media_status()
            return

        self.result_directory = ""
        self._clear_table()
        self._clear_preview()
        self._refresh_media_status()
        show_flying_message(self, f"句轴原文.txt / 句轴译文.txt not found in {self.pending_directory}")

    def _load_word_timeline(self, result_dir: Path) -> None:
        word_csv = result_dir / "merged_word_timestamps.csv"
        timeline = load_word_timeline(word_csv)
        self.word_timeline = timeline

        if timeline.bad_line_count > 0:
            show_flying_message(
                self,
                f"Skipped {timeline.bad_line_count} malformed word timestamp rows",
            )

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
            # The persistent red-light warning in the drop zone already explains this;
            # only show the transient message if the warning label is not visible.
            if not self.media_status_label.isVisible():
                show_flying_message(self, "Waveform preview needs a loaded media file")
            return

        self._cancel_worker()

        self._pending_row = row
        preview_start = aligned_row.preview_start_sec
        preview_end = aligned_row.preview_end_sec

        view_start = max(preview_start - VIEW_PADDING_SEC, 0.0)
        view_end = preview_end + VIEW_PADDING_SEC
        view_duration = view_end - view_start

        num_bins = max(int(round(view_duration * PIXELS_PER_SECOND)), 200)
        num_bins = min(num_bins, MAX_WAVEFORM_BINS)

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

        orig_entries = self._collect_sentence_entries(view_start, view_end, side="orig")
        trans_entries = self._collect_trans_entries(view_start, view_end)
        word_entries = self._collect_word_entries(view_start, view_end)

        self.waveform_widget.set_data(
            amplitudes=amplitudes,
            start_sec=view_start,
            duration_sec=view_duration,
            orig_entries=orig_entries,
            trans_entries=trans_entries,
            word_entries=word_entries,
            selected_row_key=aligned_row.row_key,
        )

        QTimer.singleShot(0, self._center_scroll_on_selection)

    def _on_waveform_error(self, error_msg: str):
        show_flying_message(self, f"Waveform error: {error_msg}")
        self.waveform_widget.clear()

    # ---------------------------------------------- Entry builders --------
    def _collect_sentence_entries(
        self,
        view_start: float,
        view_end: float,
        side: str,
    ) -> list:
        """Linear scan of aligned_rows; picks records whose [start,end] overlaps view."""
        entries: list[SentenceEntry] = []
        for aligned_row in self.aligned_rows:
            record = aligned_row.orig_record if side == "orig" else aligned_row.trans_record
            if record is None or not record.has_valid_range:
                continue
            if record.end_sec <= view_start or record.start_sec >= view_end:
                continue
            entries.append(
                SentenceEntry(
                    start_sec=float(record.start_sec),
                    end_sec=float(record.end_sec),
                    text=record.text or "",
                    row_key=aligned_row.row_key,
                )
            )
        return entries

    def _collect_trans_entries(self, view_start: float, view_end: float) -> list:
        """Build translation-track entries.

        Policy:
        - Paired 原文 row with valid range -> borrow its [start, end] so the
          trans rect aligns directly under the matching 原文 rect.
        - Unpaired trans rows (or paired with start-only orig) -> fixed 1s bar
          starting at trans.start_sec.
        - If multiple in-view trans rows share the same start (within epsilon),
          keep only the first one in aligned_rows order.
        """
        entries: list[SentenceEntry] = []
        seen_starts: list[float] = []

        for aligned_row in self.aligned_rows:
            trans = aligned_row.trans_record
            if trans is None or trans.start_sec is None:
                continue

            orig = aligned_row.orig_record
            if orig is not None and orig.has_valid_range:
                start = float(orig.start_sec)
                end = float(orig.end_sec)
            else:
                start = float(trans.start_sec)
                end = start + _TRANS_FALLBACK_DURATION_SEC

            if end <= view_start or start >= view_end:
                continue

            if any(abs(start - s) < _SAME_START_EPSILON_SEC for s in seen_starts):
                continue
            seen_starts.append(start)

            entries.append(
                SentenceEntry(
                    start_sec=start,
                    end_sec=end,
                    text=trans.text or "",
                    row_key=aligned_row.row_key,
                )
            )
        return entries

    def _collect_word_entries(self, view_start: float, view_end: float) -> list:
        timeline = self.word_timeline
        if timeline is None or timeline.is_empty():
            return []

        idx = timeline.query(view_start, view_end)
        if idx.size == 0:
            return []

        starts = timeline.starts
        ends = timeline.ends
        texts = timeline.texts
        return [
            WordEntry(
                start_sec=float(starts[i]),
                end_sec=float(ends[i]),
                text=texts[i],
            )
            for i in idx
        ]

    # ---------------------------------------------- Scroll helper --------
    def _center_scroll_on_selection(self) -> None:
        """Snap the horizontal scroll so the selected sentence is centered."""
        if not hasattr(self, "waveform_scroll"):
            return
        mid_x = self.waveform_widget.selected_sentence_midpoint_x()
        if mid_x is None:
            return
        viewport_w = self.waveform_scroll.viewport().width()
        target = max(mid_x - viewport_w // 2, 0)
        bar = self.waveform_scroll.horizontalScrollBar()
        bar.setValue(min(target, bar.maximum()))
