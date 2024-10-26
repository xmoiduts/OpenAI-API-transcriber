from PyQt5.QtWidgets import QMainWindow, QTabWidget
from .time_slicer_tab import TimeSlicerTab, get_stylesheet
from .transcription_tab import TranscriptionTab
from .transcription_new_tab import TranscriptionNewTab

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Media File Processor")
        self.setGeometry(100, 100, 600, 400)

        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        self.time_slicer_tab = TimeSlicerTab()
        self.transcription_tab = TranscriptionTab()
        self.transcription_new_tab = TranscriptionNewTab()

        self.tab_widget.addTab(self.time_slicer_tab, "Time Slicer")
        self.tab_widget.addTab(self.transcription_tab, "Transcription")
        self.tab_widget.addTab(self.transcription_new_tab, "Transcription New")

        self.setStyleSheet(get_stylesheet())

    def update_transcription_tab(self, file_path, duration):
        self.transcription_tab.update_from_other_tab({"file_path": file_path, "duration": duration})
