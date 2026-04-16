# AI-Assisted Development Note:
# To prevent Windows MAX_PATH (260 character) errors, this module must adhere to the following rule:
#
# DO NOT construct file paths for writing to disk within this file.
#
# All file-writing operations related to transcription results are delegated to the
# `WhisperTranscriber` class, which implements environment-aware path shortening.
# This GUI module receives the final, safe, absolute path of the result directory
# via the `transcription_finished` signal and stores it in `self.last_result_dir`.
#
# Any new feature requiring access to result files MUST use the path from
# `self.last_result_dir` and MUST NOT attempt to guess or reconstruct the path
# from the original media filename.

from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
                            QPushButton, QFileDialog, QTextBrowser, QProgressBar,  # 改为 QTextBrowser
                            QComboBox, QMenu, QAction, QLineEdit, QFormLayout, QDialog, QDialogButtonBox)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt, QEvent
from .tab_interface import TabInterface
from .segment_bar import SegmentBar
from .slice_manager import SliceManager, SliceStatus
from src.time_slicer.time_slicer import get_time_slices
from src.transcriber_core.transcriber import WhisperTranscriber
from .flying_message import show_flying_message
from .util.add_zero_wide_char_to_str import add_zero_wide_char_to_str
from .styles.style_manager import get_dropdown_stylesheet
import os
import sys
import subprocess
import time
import queue
import threading
import random

class SettingsDialog(QDialog):
    def __init__(self, parent=None, concurrency=4, delay=15):
        super().__init__(parent)
        self.setWindowTitle("Transcription Settings")
        self.setModal(True)
        
        layout = QFormLayout()
        
        self.concurrency_input = QLineEdit(str(concurrency))
        self.delay_input = QLineEdit(str(delay))
        
        layout.addRow("Concurrency:", self.concurrency_input)
        layout.addRow("Delay between API calls (seconds):", self.delay_input)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addWidget(buttons)
        
        self.setLayout(main_layout)
    
    def get_values(self):
        try:
            concurrency = int(self.concurrency_input.text())
            delay = int(self.delay_input.text())
            return concurrency, delay
        except ValueError:
            return None, None

class TranscriptionNewTab(TabInterface):
    def __init__(self):
        super().__init__("Transcription New")
        self.transcriber = WhisperTranscriber()
        self.config = self._load_config()
        # Add settings
        self.concurrency = 4
        self.api_delay = 30
        self.perturbation_seed = None  # Add perturbation seed storage
        self.preserve_audio_clips = False  # Add preserve audio clips flag
        self.dry_run = False  # Add dry run flag
        self.init_ui()
        self.file_path = None
        self.duration = None
        self.slices = None
        self.needs_transcoding = False  # Whether transcoding is needed
        self.target_bitrate = 128000  # Target bitrate for transcoding
        self.output_format = None  # Output format (None means keep original, 'm4a' for transcoding)
        self.log_queue = []
        self.last_result_dir = None  # Store actual result directory from backend
        
        # For transcription control
        self.transcription_in_progress = False

    def _load_config(self):
        try:
            with open('config.yaml', 'r') as f:
                import yaml
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return {}
        
    def _update_model_selector(self):
        self.model_selector.clear()
        self.model_selector.setEnabled(False)

        try:
            transcription_config = self.config.get('tasks', {})\
                .get('transcription', {})
            if not transcription_config or 'models' not in transcription_config:
                self.model_selector.addItem("---not configured---")
                self.model_selector.setEnabled(False)
                return
            models = transcription_config.get('models', {})
            for model_name in models:
                self.model_selector.addItem(model_name) 
            self.model_selector.setEnabled(True)           
        except (AttributeError, TypeError):
            self.model_selector.addItem("---not configured---")
            return
            


    def _on_model_changed(self, selected_model):
        #if not self.provider_selector: return
        self.provider_selector.clear()
        
        if selected_model in ["---not configured---", ""]:
            self.provider_selector.addItem("---invalid model---")
            self.provider_selector.setEnabled(False)
            return
            
        # Get providers for selected model
        model_providers = self.config.get('api', {}).get('models', {})\
            .get(selected_model, {}).get('providers', {})
        
        if not model_providers:
            self.provider_selector.addItem("---invalid model---")
            self.provider_selector.setEnabled(False)
            return
            
        self.provider_selector.setEnabled(True)
        for provider in model_providers:
            self.provider_selector.addItem(provider)

    def init_ui(self):
        # Main vertical layout
        layout = QVBoxLayout()
        
        # Top section for file info and segment bar
        top_section = QVBoxLayout()
        self.file_info_label = QLabel("No file selected")
        self.file_info_label.setWordWrap(True)
        top_section.addWidget(self.file_info_label)
        self.segment_bar = SegmentBar(mode="transcription")
        # Connect perturbation signal
        self.segment_bar.perturbation_changed.connect(self.set_perturbation_seed)
        top_section.addWidget(self.segment_bar)
        
        # Progress section
        progress_section = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()  # Initially hidden
        progress_section.addWidget(self.progress_bar)
        
        # Middle section for log
        middle_section = QVBoxLayout()
        self.log_display = QTextBrowser()
        self.log_display.setOpenExternalLinks(False)
        middle_section.addWidget(self.log_display)
        self.cursor = self.log_display.textCursor()
        
        # Bottom section for buttons
        bottom_section = QHBoxLayout()
        #   Model's provider Selection | dropdown menu
        provider_label = QLabel("Provider:")
        self.provider_selector = QComboBox()
        self.provider_selector.setStyleSheet(get_dropdown_stylesheet())
        self.provider_selector.setEnabled(False)
        #   Model Selection | dropdown menu
        model_label = QLabel("Model:")
        self.model_selector = QComboBox()
        self.model_selector.setStyleSheet(get_dropdown_stylesheet())
        self.model_selector.currentTextChanged.connect(self._on_model_changed)
        self._update_model_selector()
        #   Settings button
        self.settings_button = QPushButton("⚙")
        self.settings_button.setObjectName("settings_button")
        self.settings_button.setFixedSize(32, 32)
        self.settings_button.clicked.connect(self.show_settings_dialog)
        self.settings_button.setContextMenuPolicy(Qt.CustomContextMenu)
        self.settings_button.customContextMenuRequested.connect(self.show_settings_menu)
        #   Transcribe button
        self.transcribe_button = QPushButton("Transcribe")
        self.transcribe_button.clicked.connect(self.start_transcription)
        self.transcribe_button.setEnabled(False) # Disable initially
        # Add hover behavior for transcribe button
        self.transcribe_button.installEventFilter(self)
        #   Stop button
        self.stop_button = QPushButton("⏹")
        self.stop_button.setObjectName("stop_button")
        self.stop_button.clicked.connect(self.stop_transcription)
        self.stop_button.setEnabled(False)  # Initially disabled
        self.stop_button.setFixedSize(32, 32)  # Make button square
        # Add to bottom section
        bottom_section.addStretch()
        bottom_section.addWidget(model_label)
        bottom_section.addWidget(self.model_selector)
        bottom_section.addStretch()
        bottom_section.addWidget(provider_label)
        bottom_section.addWidget(self.provider_selector)
        bottom_section.addStretch()
        bottom_section.addWidget(self.settings_button)
        bottom_section.addWidget(self.stop_button)
        bottom_section.addWidget(self.transcribe_button)
        
        # Add all sections to main layout
        layout.addLayout(top_section)
        layout.addLayout(progress_section)
        layout.addLayout(middle_section, stretch=1)  # Give log window stretch priority
        layout.addLayout(bottom_section)

        self.setLayout(layout)

    def eventFilter(self, obj, event):
        """Handle hover events for transcribe button"""
        if obj == self.transcribe_button:
            if event.type() == QEvent.Enter and not self.transcription_in_progress:
                self.mark_slices_for_transcription()
            elif event.type() == QEvent.Leave and not self.transcription_in_progress:
                self.segment_bar.clear_marked_slices()
        return super().eventFilter(obj, event)
    
    def mark_slices_for_transcription(self):
        """Mark slices for transcription based on current selection state"""
        if not hasattr(self.segment_bar, 'slice_manager'):
            return
            
        slice_manager = self.segment_bar.slice_manager
        selected_slices = slice_manager.get_selected_slices()
        
        if selected_slices:
            # If there are selected slices, mark only those
            self.segment_bar.set_marked_slices(selected_slices)
        else:
            # If no selected slices, mark all transcribable slices
            transcribable_slices = slice_manager.get_transcribable_slices()
            self.segment_bar.set_marked_slices(transcribable_slices)

    def update_from_other_tab(self, data):
        self.file_path = data.get("file_path")
        self.duration = data.get("duration")
        self.slices = data.get("slices")
        self.needs_transcoding = data.get("needs_transcoding", False)
        self.target_bitrate = data.get("effective_bitrate", 128000)
        self.output_format = data.get("output_format")
        if self.file_path and self.duration:
            # Format file path to show only the last part if too long
            file_name = self.file_path.split('/')[-1]  # Get just the filename
            # Insert zero-width spaces at path separators for better wrapping
            display_path = add_zero_wide_char_to_str(self.file_path)
            self.file_info_label.setText(
                f"File: {display_path} | Duration: {self.duration:.2f}s")
            self.transcribe_button.setEnabled(True)
        else:
            self.file_info_label.setText("No file selected")
            # Disable the button when no file is selected
            self.transcribe_button.setEnabled(False)  
        if self.file_path and self.duration:
            self.segment_bar.set_segments(self.slices, self.needs_transcoding, self.target_bitrate)
        else:
            self.segment_bar.set_segments([])

    def replace_slices(self, file_path, duration, slices):
        """Replace only the slice data, preserving transcoding settings."""
        self.file_path = file_path
        self.duration = duration
        self.slices = slices
        if self.file_path and self.duration:
            display_path = add_zero_wide_char_to_str(self.file_path)
            self.file_info_label.setText(
                f"File: {display_path} | Duration: {self.duration:.2f}s")
            self.transcribe_button.setEnabled(True)
            self.segment_bar.set_segments(
                self.slices,
                self.needs_transcoding,
                self.target_bitrate,
            )
        else:
            self.file_info_label.setText("No file selected")
            self.transcribe_button.setEnabled(False)
            self.segment_bar.set_segments([])

    def start_transcription(self):
        if not self.file_path or not self.duration or not self.slices:
            show_flying_message(self, "Missing required information")
            return

        # Get slices to transcribe based on selection/marking
        slice_manager = self.segment_bar.slice_manager
        selected_slices = slice_manager.get_selected_slices()
        
        if selected_slices:
            # Transcribe only selected slices
            slices_to_transcribe = selected_slices
        else:
            # Transcribe all transcribable slices
            slices_to_transcribe = slice_manager.get_transcribable_slices()
        
        if not slices_to_transcribe:
            show_flying_message(self, "No slices available for transcription")
            return

        try:
            selected_model = self.model_selector.currentText()
            selected_provider = self.provider_selector.currentText()
            if selected_model in ["---not configured---"] or \
                selected_provider in ["---invalid model---"]:
                    show_flying_message(self, "Invalid model or provider selection")
                    return
            assert self.transcriber.set_model_and_provider(selected_model, selected_provider) is True

            self.transcribe_button.setEnabled(False)
            self.transcription_in_progress = True
            self.progress_bar.setValue(0)
            self.progress_bar.show()
            self.log_display.clear()
            
            # Keep marked slices during transcription
            self.segment_bar.set_marked_slices(slices_to_transcribe)
            
            # Set selected slices to transcribing status
            for slice_idx in slices_to_transcribe:
                slice_manager.set_slice_status(slice_idx, SliceStatus.SELECTED)

            # Get slice data for transcription
            all_slices, all_offsets = slice_manager.get_legacy_format()
            slices_for_transcription = [(all_slices[i], all_offsets[i]) for i in slices_to_transcribe]

            # Create and start the transcription thread
            self.transcription_thread = TranscriptionThread(
                self.transcriber, 
                self.file_path, 
                slices_for_transcription,
                slices_to_transcribe,  # Pass slice indices
                slice_manager,
                self.concurrency,
                self.api_delay,
                self.perturbation_seed,  # Pass perturbation seed
                self.needs_transcoding,  # Pass transcoding flag
                self.target_bitrate,  # Pass target bitrate
                self.output_format,  # Pass output format
                self.preserve_audio_clips,  # Pass preserve audio clips flag
                self.dry_run  # Pass dry run flag
            )
            self.transcription_thread.log_signal.connect(self.update_log)
            self.transcription_thread.finished_signal.connect(self.transcription_finished)
            self.transcription_thread.progress_signal.connect(self.progress_bar.setValue)
            self.transcription_thread.start()

            self.stop_button.setEnabled(True)

        except Exception as e:
            import traceback
            error_message = f"Error during transcription: {str(e)}\n\nCall Stack:\n{traceback.format_exc()}"
            self.update_log(error_message)
            self.transcribe_button.setEnabled(True)
            self.transcription_in_progress = False

    def update_segment_status(self, segment_index, status):
        """Update the status of a specific segment in the segment bar"""
        current_statuses = self.segment_bar.segment_status.copy()
        current_statuses[segment_index] = status
        self.segment_bar.set_segment_status(current_statuses)

    def log_callback(self, message):
        self.log_queue.append(message)

    def update_log(self, message):
        self.cursor.movePosition(self.cursor.End)
        self.cursor.insertText(message)
        self.cursor.insertHtml("<br>")
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum()
        )
    
    def _get_result_directory(self):
        """Returns the actual result directory from the last successful transcription."""
        if not self.last_result_dir:
            self.update_log("Result directory not available. Please run a transcription first.")
            return None
        
        if not os.path.exists(self.last_result_dir):
            self.update_log(f"Directory not found: {self.last_result_dir}")
            return None
            
        return self.last_result_dir

    def open_result_directory(self):
        result_dir = self._get_result_directory()
        if not result_dir:
            return
            
        try:
            if sys.platform == "win32":
                os.startfile(result_dir)
            else: # not tested
                import subprocess
                subprocess.Popen(["xdg-open", result_dir]) 
        except Exception as e:
            self.update_log(f"Error opening directory: {str(e)}")

    def open_in_vscode(self):
        result_dir = self._get_result_directory()
            
        try:
            subprocess.run(
                ["code", "."],
                cwd=result_dir,
                check=True,
                shell=True,  # 使用 shell 执行
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            self.update_log("VSCode not found in system PATH")
        except Exception as e:
            self.update_log(f"Error opening VSCode: {str(e)}")

    def open_in_cursor(self):
        result_dir = self._get_result_directory()
        if not result_dir:
            return
            
        try:
            subprocess.run(
                ["cursor", "."],
                cwd=result_dir,
                check=True,
                shell=True,  # 使用 shell 执行
                capture_output=True,
                text=True,
            )
        except FileNotFoundError:
            self.update_log("Cursor not found in system PATH")
        except Exception as e:
            self.update_log(f"Error opening Cursor: {str(e)}")

    def handle_link_click(self, url):
        action = url.toString()
        if action == 'open_dir':
            self.open_result_directory()
        elif action == 'open_vscode':
            self.open_in_vscode()
        elif action == 'open_cursor':
            self.open_in_cursor()

    def transcription_finished(self, success, result_dir=""):
        if success and result_dir:
            self.last_result_dir = result_dir  # Store the actual result directory
            self.update_log("\nTranscription completed successfully B")
            self.update_log("Actions:")
            # 安全地断开旧的连接
            try:
                self.log_display.anchorClicked.disconnect(self.handle_link_click)
            except TypeError:  # 如果信号未连接，会抛出 TypeError
                pass
            
            self.log_display.insertHtml(" • <a href='open_dir'>Open Result Directory</a><br>")
            self.log_display.insertHtml(" • <a href='open_vscode'>Open in VSCode</a><br>")
            self.log_display.insertHtml(" • <a href='open_cursor'>Open in Cursor</a><br>")
            self.log_display.setReadOnly(True)
            self.log_display.anchorClicked.connect(self.handle_link_click)
            self.log_display.setOpenLinks(False)
            self.log_display.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextBrowserInteraction
            )
        else:
            self.update_log("Transcription failed")
        
        self.transcribe_button.setEnabled(True)
        self.transcription_in_progress = False
        self.progress_bar.hide()
        self.stop_button.setEnabled(False)
        # Clear marked slices when transcription is done
        self.segment_bar.clear_marked_slices()

    def stop_transcription(self):
        if hasattr(self, 'transcription_thread'):
            self.transcription_thread.stop_requested = True
            self.stop_button.setEnabled(False)
            self.update_log("\nStopping transcription after current segment...")

    def show_settings_dialog(self):
        """Show settings dialog when left-clicking the settings button"""
        self.show_settings_menu(self.settings_button.rect().bottomLeft())
    
    def show_settings_menu(self, position):
        """Show context menu for settings"""
        menu = QMenu(self)
        
        # Create form-like menu items
        concurrency_action = QAction(f"Concurrency: {self.concurrency}", self)
        delay_action = QAction(f"API Delay: {self.api_delay}s", self)
        
        # Add preserve audio clips checkbox
        preserve_clips_action = QAction("Preserve cut audio clips", self)
        preserve_clips_action.setCheckable(True)
        preserve_clips_action.setChecked(self.preserve_audio_clips)
        
        # Add dry run checkbox
        dry_run_action = QAction("Dry Run (Clip only)", self)
        dry_run_action.setCheckable(True)
        dry_run_action.setChecked(self.dry_run)
        dry_run_action.setToolTip("Process audio clips without sending to transcription API")
        dry_run_action.setStatusTip("Process audio clips without sending to transcription API")
        
        concurrency_action.triggered.connect(lambda: self.edit_setting('concurrency'))
        delay_action.triggered.connect(lambda: self.edit_setting('delay'))
        preserve_clips_action.triggered.connect(lambda: self.toggle_preserve_clips(preserve_clips_action.isChecked()))
        dry_run_action.triggered.connect(lambda: self.toggle_dry_run(dry_run_action.isChecked()))
        
        menu.addAction(concurrency_action)
        menu.addAction(delay_action)
        menu.addSeparator()
        menu.addAction(preserve_clips_action)
        menu.addAction(dry_run_action)
        
        # Show menu at global position
        global_pos = self.settings_button.mapToGlobal(position)
        menu.exec_(global_pos)
    
    def edit_setting(self, setting_type):
        """Edit a specific setting"""
        dialog = SettingsDialog(self, self.concurrency, self.api_delay)
        
        if dialog.exec_() == QDialog.Accepted:
            concurrency, delay = dialog.get_values()
            if concurrency is not None and delay is not None:
                self.concurrency = max(1, concurrency)  # Ensure at least 1
                self.api_delay = max(0, delay)  # Ensure non-negative
                show_flying_message(self, f"Settings updated: Concurrency={self.concurrency}, Delay={self.api_delay}s")

    def toggle_preserve_clips(self, checked):
        """Toggle preserve audio clips setting"""
        self.preserve_audio_clips = checked
        status = "enabled" if checked else "disabled"
        show_flying_message(self, f"Preserve audio clips {status}")

    def toggle_dry_run(self, checked):
        """Toggle dry run setting"""
        self.dry_run = checked
        status = "enabled" if checked else "disabled"
        show_flying_message(self, f"Dry run {status}")

    def set_perturbation_seed(self, seed):
        """Set the perturbation seed for audio processing."""
        self.perturbation_seed = seed
        if seed is not None:
            show_flying_message(self, f"Perturbation enabled with seed: {seed:04x}")
        else:
            show_flying_message(self, "Perturbation disabled")

class TranscriptionThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)  # Include result directory path
    progress_signal = pyqtSignal(int)
    slice_completed_signal = pyqtSignal()  # Signal for real-time progress update

    def __init__(self, transcriber, file_path, slices_with_offsets, slice_indices, 
                 slice_manager, concurrency, api_delay, perturbation_seed=None,
                 needs_transcoding=False, target_bitrate=128000, output_format=None,
                 preserve_audio_clips=False, dry_run=False):
        super().__init__()
        self.transcriber = transcriber
        self.file_path = file_path
        self.slices_with_offsets = slices_with_offsets  # [(slice_data, actual_start), ...]
        self.slice_indices = slice_indices  # [index, ...] - original indices for status updates
        self.slice_manager = slice_manager
        self.concurrency = concurrency
        self.api_delay = api_delay
        self.perturbation_seed = perturbation_seed  # Store perturbation seed
        self.needs_transcoding = needs_transcoding  # Whether transcoding is needed
        self.target_bitrate = target_bitrate  # Target bitrate for transcoding
        self.output_format = output_format  # Output format (None or 'm4a')
        self.preserve_audio_clips = preserve_audio_clips  # Store preserve audio clips flag
        self.dry_run = dry_run  # Store dry run flag
        self.stop_requested = False
        
        # For managing concurrent transcription
        self.completed_slices = 0
        self.total_slices = len(slices_with_offsets)
        self.active_threads = 0
        self.lock = threading.Lock()
        self.result_queue = queue.Queue()
        self.last_successful_result_dir = None  # Track the result directory

        self.slice_completed_signal.connect(self._on_slice_completed)
    
    def _on_slice_completed(self):
        """Thread-safe method to update progress as each slice finishes."""
        with self.lock:
            self.completed_slices += 1
            progress = int((self.completed_slices / self.total_slices) * 100)
            self.progress_signal.emit(progress)
    
    def _drain_log_queue(self):
        """Continuously drain the log queue and emit log signals."""
        while True:
            try:
                msg_type, msg = self.result_queue.get(timeout=0.1)
                if msg_type == 'log':
                    self.log_signal.emit(msg)
                elif msg_type == 'stop':
                    break
            except queue.Empty:
                if self.stop_requested or not threading.main_thread().is_alive():
                    break
                continue

    def run(self):
        try:
            if self.concurrency <= 1:
                # Serial processing
                self.run_serial()
            else:
                # Parallel processing
                self.run_parallel()
                
        except Exception as e:
            self.log_signal.emit(f"Error during transcription: {str(e)}")
            self.finished_signal.emit(False)
    
    def run_serial(self):
        """Run transcription serially (original behavior)"""
        for i, ((slice_start, duration), actual_start) in enumerate(self.slices_with_offsets):
            if self.stop_requested:
                self.log_signal.emit("\nTranscription stopped by user")
                self.finished_signal.emit(False)
                return

            slice_index = self.slice_indices[i]
            # Set status to transcribing just before processing
            self.slice_manager.set_slice_status(slice_index, SliceStatus.TRANSCRIBING)
            self.log_signal.emit(f"\nProcessing segment {i+1}/{self.total_slices} (slice {slice_index})")
            self.log_signal.emit(f"Slice start: {slice_start}s, Actual start: {actual_start}s, Duration: {duration}s")
            
            result_data = self.transcriber.transcribe(
                input_file=self.file_path,
                display_start=slice_start,
                actual_start=actual_start,
                duration=int(duration),
                log_callback=self.log_signal.emit,
                perturbation_seed=self.perturbation_seed,  # Pass perturbation seed
                needs_transcoding=self.needs_transcoding,  # Pass transcoding flag
                target_bitrate=self.target_bitrate,  # Pass target bitrate
                output_format=self.output_format,  # Pass output format
                preserve_audio_clips=self.preserve_audio_clips,  # Pass preserve audio clips flag
                dry_run=self.dry_run  # Pass dry run flag
            )
            
            if result_data is None:
                self.slice_manager.set_slice_status(slice_index, SliceStatus.FAILURE)
                self.log_signal.emit(f"Failed to transcribe segment {i+1}")
                self.finished_signal.emit(False, "")
                return
            
            # Store the result directory from the successful transcription
            self.last_successful_result_dir = result_data["result_dir"]
            
            self.slice_manager.set_slice_status(slice_index, SliceStatus.DONE)
            # Use the connected slot to update progress
            self._on_slice_completed()

            # Apply rate control
            if i < self.total_slices - 1:  # Don't delay after the last slice
                time.sleep(self.api_delay)
        
        self.finished_signal.emit(True, self.last_successful_result_dir or "")
    
    def run_parallel(self):
        """Run transcription with limited concurrency"""
        import concurrent.futures
        
        # Adjust concurrency to not exceed the number of slices
        actual_concurrency = min(self.concurrency, self.total_slices)
        self.log_signal.emit(f"Starting parallel transcription with concurrency: {actual_concurrency}")
        
        # Start a thread to drain the log queue
        log_thread = threading.Thread(target=self._drain_log_queue, daemon=True)
        log_thread.start()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=actual_concurrency) as executor:
            # Submit all tasks
            future_to_index = {}
            for i, ((slice_start, duration), actual_start) in enumerate(self.slices_with_offsets):
                if self.stop_requested:
                    break
                    
                # Apply delay between submissions
                if i > 0:
                    time.sleep(self.api_delay)
                
                # Set status to transcribing just before submitting to executor
                slice_index = self.slice_indices[i]
                self.slice_manager.set_slice_status(slice_index, SliceStatus.TRANSCRIBING)

                future = executor.submit(
                    self.transcribe_single_slice,
                    i, slice_start, duration, actual_start
                )
                future_to_index[future] = i
            
            # Process completed tasks
            for future in concurrent.futures.as_completed(future_to_index):
                if self.stop_requested:
                    # Cancel remaining futures
                    for f in future_to_index:
                        f.cancel()
                    break
                
                try:
                    result_data = future.result()
                    if not result_data.get("success"):
                        self.log_signal.emit(f"Transcription failed for slice {future_to_index[future]}. Stopping all tasks.")
                        # Stop the log thread
                        self.result_queue.put(('stop', None))
                        log_thread.join(timeout=1)
                        self.finished_signal.emit(False, "")
                        # Cancel remaining futures
                        for f in future_to_index:
                            f.cancel()
                        return
                    
                    # Store the last successful result directory
                    if result_data.get("result_dir"):
                        self.last_successful_result_dir = result_data["result_dir"]
                        
                except Exception as e:
                    self.log_signal.emit(f"Error in parallel transcription: {str(e)}")
                    # Stop the log thread
                    self.result_queue.put(('stop', None))
                    log_thread.join(timeout=1)
                    self.finished_signal.emit(False, "")
                    return
        
        # Stop the log thread
        self.result_queue.put(('stop', None))
        log_thread.join(timeout=1)
        
        if self.stop_requested:
            self.log_signal.emit("\nTranscription stopped by user")
            self.finished_signal.emit(False, "")
        else:
            self.finished_signal.emit(True, self.last_successful_result_dir or "")
    
    def transcribe_single_slice(self, task_index, slice_start, duration, actual_start):
        """Transcribe a single slice (used by parallel processing)"""
        if self.stop_requested:
            return {"success": False, "result_dir": None}
            
        slice_index = self.slice_indices[task_index]
        
        # Log start of processing
        self.result_queue.put(('log', f"\nProcessing segment {task_index+1}/{self.total_slices} (slice {slice_index})"))
        self.result_queue.put(('log', f"Slice start: {slice_start}s, Actual start: {actual_start}s, Duration: {duration}s"))
        
        # Set status to transcribing
        self.slice_manager.set_slice_status(slice_index, SliceStatus.TRANSCRIBING)
        
        result_data = self.transcriber.transcribe(
            input_file=self.file_path,
            display_start=slice_start,
            actual_start=actual_start,
            duration=int(duration),
            log_callback=lambda msg: self.result_queue.put(('log', msg)),
            perturbation_seed=self.perturbation_seed,  # Pass perturbation seed
            needs_transcoding=self.needs_transcoding,  # Pass transcoding flag
            target_bitrate=self.target_bitrate,  # Pass target bitrate
            output_format=self.output_format,  # Pass output format
            preserve_audio_clips=self.preserve_audio_clips,  # Pass preserve audio clips flag
            dry_run=self.dry_run  # Pass dry run flag
        )
        
        if result_data is None:
            self.slice_manager.set_slice_status(slice_index, SliceStatus.FAILURE)
            self.result_queue.put(('log', f"Failed to transcribe segment {task_index+1}"))
            # Do not emit progress signal here, let the main loop handle failure
            return {"success": False, "result_dir": None}
        
        self.slice_manager.set_slice_status(slice_index, SliceStatus.DONE)
        self.result_queue.put(('log', f"Completed slice {slice_index}"))
        # Emit signal to notify progress update
        self.slice_completed_signal.emit()
        return {"success": True, "result_dir": result_data["result_dir"]}