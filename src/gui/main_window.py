from PyQt5.QtWidgets import QMainWindow, QTabWidget
from .time_slicer_tab import TimeSlicerTab
from .transcription_tab import TranscriptionTab
from .transcription_new_tab import TranscriptionNewTab
from .ASR_postprocess_tab import ASRPostprocessTab
from .sentence_builder_tab import SentenceBuilderTab
from .line_translation_tab import LineTranslationTab
from .sentence_aligner_tab import SentenceAlignerTab
from .styles.style_manager import get_main_window_stylesheet


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Media File Processor")
        self.setGeometry(100, 100, 1024, 768)

        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        self.time_slicer_tab = TimeSlicerTab()
        self.transcription_tab = TranscriptionTab()
        self.transcription_new_tab = TranscriptionNewTab()
        self.asr_postprocess_tab = ASRPostprocessTab()
        self.sentence_builder_tab = SentenceBuilderTab()
        self.line_translation_tab = LineTranslationTab()
        self.sentence_aligner_tab = SentenceAlignerTab()

        self.tab_widget.addTab(self.time_slicer_tab, "Time Slicer")
        self.tab_widget.addTab(self.transcription_tab, "Tr-old")
        self.tab_widget.addTab(self.transcription_new_tab, "Transcription New")
        self.tab_widget.addTab(self.asr_postprocess_tab, "ASR post process")
        self.tab_widget.addTab(self.sentence_builder_tab, "Sentence Builder")
        self.tab_widget.addTab(self.line_translation_tab, "Line Translation")
        self.tab_widget.addTab(self.sentence_aligner_tab, "Sentence Aligner")

        self.setStyleSheet(get_main_window_stylesheet())

    def update_transcription_tab(self, file_path, duration, slices, needs_transcoding=False, effective_bitrate=0, output_format=None):
        data = {
            "file_path": file_path, 
            "duration": duration, 
            "slices": slices,
            "needs_transcoding": needs_transcoding,
            "effective_bitrate": effective_bitrate,
            "output_format": output_format
        }
        self.transcription_tab.update_from_other_tab(data)
        self.transcription_new_tab.update_from_other_tab(data)
        self.asr_postprocess_tab.update_from_other_tab(data)
        self.sentence_builder_tab.update_from_other_tab(data)
        self.sentence_aligner_tab.update_from_other_tab(data)

