from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from .tab_interface import TabInterface

class TranscriptionNewTab(TabInterface):
    def __init__(self):
        super().__init__("Transcription New")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        label = QLabel("This is the new transcription tab.")
        layout.addWidget(label)
        self.setLayout(layout)

    def update_from_other_tab(self, data):
        # Implement this method if needed
        pass