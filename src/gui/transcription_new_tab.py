from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, 
                           QFileDialog, QTextEdit, QProgressBar)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
from .tab_interface import TabInterface
from .segment_bar import SegmentBar
from src.time_slicer.time_slicer import get_time_slices
from src.transcriber_core.transcriber import WhisperTranscriber
from .flying_message import show_flying_message
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
        layout = QVBoxLayout()
        self.file_info_label = QLabel("No file selected")
        layout.addWidget(self.file_info_label)

        self.segment_bar = SegmentBar(mode="transcription")
        layout.addWidget(self.segment_bar)

        # Transcription button
        self.transcribe_button = QPushButton("Start Transcribe")
        self.transcribe_button.clicked.connect(self.start_transcription)
        self.transcribe_button.setEnabled(False) # Disable initially
        layout.addWidget(self.transcribe_button)

        self.setLayout(layout)

    def update_from_other_tab(self, data):
        self.file_path = data.get("file_path")
        self.duration = data.get("duration")
        self.slices = data.get("slices")
        if self.file_path and self.duration:
            self.file_info_label.setText(
                f"File: {self.file_path}\n"
                f"Duration: {self.duration:.2f} seconds")
            # Enable the button when a file is selected
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
        if not self.file_path:
            show_flying_message(self, "No file selected")
            return
        if not self.duration:
            show_flying_message(self, "No duration information")
            return

        try:
            self.transcribe_button.setEnabled(False)

            # Clear previous log display if it exists
            if hasattr(self, 'log_display'):
                self.layout().removeWidget(self.log_display)
                self.log_display.deleteLater()
                self.log_display = None

            # New log display
            self.log_display = QTextEdit()
            self.log_display.setReadOnly(True)
            self.layout().addWidget(self.log_display)

            # Create and start the transcription thread
            self.transcription_thread = TranscriptionThread(self.transcriber, self.file_path, self.duration)
            self.transcription_thread.log_signal.connect(self.update_log)
            self.transcription_thread.finished_signal.connect(self.transcription_finished)
            self.transcription_thread.start()

        except Exception as e:
            import traceback
            error_message = f"Error during transcription: {str(e)}\n\nCall Stack:\n{traceback.format_exc()}"
            self.log_display.append(error_message)
            self.transcribe_button.setEnabled(True)

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

class TranscriptionThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool)

    def __init__(self, transcriber, file_path, duration):
        super().__init__()
        self.transcriber = transcriber
        self.file_path = file_path
        self.duration = duration

    def run(self):
        result = self.transcriber.transcribe(
            input_file=self.file_path,
            start_time=0,
            duration=int(self.duration),
            log_callback=self.log_signal.emit
        )
        self.finished_signal.emit(result is not None)