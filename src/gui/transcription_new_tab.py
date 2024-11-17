from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
                            QPushButton, QFileDialog, QTextEdit, QProgressBar)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
from .tab_interface import TabInterface
from .segment_bar import SegmentBar
from src.time_slicer.time_slicer import get_time_slices
from src.transcriber_core.transcriber import WhisperTranscriber
from .flying_message import show_flying_message
from .util.add_zero_wide_char_to_str import add_zero_wide_char_to_str
class TranscriptionNewTab(TabInterface):
    def __init__(self):
        super().__init__("Transcription New")
        self.transcriber = WhisperTranscriber()
        self.init_ui()
        self.file_path = None
        self.duration = None
        self.slices = None
        self.log_queue = []

    def init_ui(self):
        # Main vertical layout
        layout = QVBoxLayout()
        
        # Top section for file info and segment bar
        top_section = QVBoxLayout()
        self.file_info_label = QLabel("No file selected")
        self.file_info_label.setWordWrap(True)
        top_section.addWidget(self.file_info_label)
        self.segment_bar = SegmentBar(mode="transcription")
        top_section.addWidget(self.segment_bar)
        
        # Progress section
        progress_section = QVBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()  # Initially hidden
        progress_section.addWidget(self.progress_bar)
        
        # Middle section for log
        middle_section = QVBoxLayout()
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        middle_section.addWidget(self.log_display)
        
        # Bottom section for buttons
        bottom_section = QHBoxLayout()
        self.transcribe_button = QPushButton("Transcribe")
        self.transcribe_button.clicked.connect(self.start_transcription)
        self.transcribe_button.setEnabled(False) # Disable initially
        bottom_section.addStretch()
        bottom_section.addWidget(self.transcribe_button)
        
        # Add all sections to main layout
        layout.addLayout(top_section)
        layout.addLayout(progress_section)
        layout.addLayout(middle_section, stretch=1)  # Give log window stretch priority
        layout.addLayout(bottom_section)

        self.setLayout(layout)

    def update_from_other_tab(self, data):
        self.file_path = data.get("file_path")
        self.duration = data.get("duration")
        self.slices = data.get("slices")
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
            self.segment_bar.set_segments(self.slices)
        else:
            self.segment_bar.set_segments([])

    def start_transcription(self):
        slices = self.segment_bar.segments
        segment_offsets = self.segment_bar.segment_start_offsets
        assert len(slices) == len(segment_offsets)
        if not self.file_path or not self.duration or not slices:
            show_flying_message(self, "Missing required information")
            return

        try:
            self.transcribe_button.setEnabled(False)
            self.progress_bar.setValue(0)
            self.progress_bar.show()
            self.log_display.clear()
            
            # Initialize segment statuses
            self.segment_bar.set_segment_status({i: "pending" for i in range(len(slices))})

            # Create and start the transcription thread
            self.transcription_thread = TranscriptionThread(
                self.transcriber, 
                self.file_path, 
                slices,
                segment_offsets
            )
            self.transcription_thread.log_signal.connect(self.update_log)
            self.transcription_thread.finished_signal.connect(self.transcription_finished)
            self.transcription_thread.progress_signal.connect(self.progress_bar.setValue)
            self.transcription_thread.segment_status_signal.connect(self.update_segment_status)
            self.transcription_thread.start()

        except Exception as e:
            import traceback
            error_message = f"Error during transcription: {str(e)}\n\nCall Stack:\n{traceback.format_exc()}"
            self.log_display.append(error_message)
            self.transcribe_button.setEnabled(True)

    def update_segment_status(self, segment_index, status):
        """Update the status of a specific segment in the segment bar"""
        current_statuses = self.segment_bar.segment_status.copy()
        current_statuses[segment_index] = status
        self.segment_bar.set_segment_status(current_statuses)

    def log_callback(self, message):
        self.log_queue.append(message)

    def update_log(self, message):
        self.log_display.append(message)
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum()
        )

    def transcription_finished(self, success):
        if success:
            self.log_display.append("Transcription completed successfully")
        else:
            self.log_display.append("Transcription failed")
        self.transcribe_button.setEnabled(True)
        self.progress_bar.hide()

class TranscriptionThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)
    progress_signal = pyqtSignal(int)
    segment_status_signal = pyqtSignal(int, str)  # New signal for segment status updates

    def __init__(self, transcriber, file_path, slices, actual_starts):
        super().__init__()
        self.transcriber = transcriber
        self.file_path = file_path
        self.slices = slices # list of (start: int?, duration: int?)
        self.actual_starts = actual_starts # list of int, len == slices
        assert len(self.slices) == len(self.actual_starts)

    def run(self):
        try:
            total_slices = len(self.slices)
            for i, (slice_start, duration) in enumerate(self.slices):
                self.segment_status_signal.emit(i, "in_progress")
                self.log_signal.emit(f"\nProcessing segment {i+1}/{total_slices}")
                actual_start = self.actual_starts[i]
                self.log_signal.emit(f"Slice start: {slice_start}s,\
                                      Actual start: {actual_start}s,\
                                          Duration: {duration}s")
                
                result = self.transcriber.transcribe(
                    input_file=self.file_path,
                    display_start=slice_start,
                    actual_start=actual_start,
                    duration=int(duration),
                    log_callback=self.log_signal.emit
                )
                
                if result is None:
                    self.segment_status_signal.emit(i, "error")
                    self.log_signal.emit(f"Failed to transcribe segment {i+1}")
                    self.finished_signal.emit(False)
                    return
                
                self.segment_status_signal.emit(i, "completed")
                progress = int(((i + 1) / total_slices) * 100)
                self.progress_signal.emit(progress)
                import time # delay 30 seconds before launching next transcribe request, for API throttling.
                time.sleep(30)
            
            self.finished_signal.emit(True)
        except Exception as e:
            self.segment_status_signal.emit(i, "error")
            self.log_signal.emit(f"Error during transcription: {str(e)}")
            self.finished_signal.emit(False)