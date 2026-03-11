from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QFrame, QHBoxLayout, QPushButton

from .tab_interface import TabInterface
from .styles.style_manager import get_drop_zone_stylesheet, get_scrollbar_stylesheet
from .util.add_zero_wide_char_to_str import add_zero_wide_char_to_str
from .vad_exp.audio_parse_thread import AudioParseThread
from .vad_exp.timeline_widgets import VadMethodSpec, VadTimelinePanel


APPROVAL_THRESHOLD_SEC = 10 * 60


class VADExpTab(TabInterface):
    """Experimental tab for comparing multiple future VAD implementations."""

    def __init__(self):
        super().__init__("VAD Exp")
        self.current_file_path = ""
        self.current_duration = 0.0
        self.pending_approval = False
        self.parse_generation = 0
        self.parse_thread = None
        self.method_specs = [
            VadMethodSpec(
                method_key="vad_method_1",
                title="VAD Method 1",
                accent_color="#4A90D9",
                description="Real audio-strength tiles with placeholder VAD intervals.",
            ),
            VadMethodSpec(
                method_key="vad_method_2",
                title="VAD Method 2",
                accent_color="#43A047",
                description="Second comparison lane sharing the same time viewport.",
            ),
            VadMethodSpec(
                method_key="vad_method_3",
                title="VAD Method 3",
                accent_color="#FB8C00",
                description="Third comparison lane for future VAD experiments.",
            ),
        ]
        self.init_ui()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        self.file_info_label = QLabel("Waiting for broadcast from Time Slicer")
        self.file_info_label.setProperty("dropZone", True)
        self.file_info_label.setAlignment(Qt.AlignCenter)
        self.file_info_label.setWordWrap(True)
        self.file_info_label.setFixedHeight(72)
        root_layout.addWidget(self.file_info_label)

        note_frame = QFrame()
        note_frame.setObjectName("vadExpNote")
        note_layout = QVBoxLayout(note_frame)
        note_layout.setContentsMargins(10, 8, 10, 8)
        note_layout.setSpacing(4)
        note_layout.addWidget(QLabel("Experimental multi-VAD comparison area"))
        note_layout.addWidget(
            QLabel("Current round: fixed finest scale, tiled synthetic strength, overlay VAD, no parsing / zoom yet")
        )
        root_layout.addWidget(note_frame)

        gate_frame = QFrame()
        gate_frame.setObjectName("vadApprovalGate")
        gate_layout = QHBoxLayout(gate_frame)
        gate_layout.setContentsMargins(10, 8, 10, 8)
        gate_layout.setSpacing(8)
        self.parse_status_label = QLabel("Waiting for media broadcast")
        self.parse_status_label.setWordWrap(True)
        gate_layout.addWidget(self.parse_status_label, stretch=1)
        self.approve_button = QPushButton("Approve")
        self.approve_button.clicked.connect(self._on_approve_clicked)
        self.approve_button.hide()
        gate_layout.addWidget(self.approve_button)
        root_layout.addWidget(gate_frame)

        self.timeline_panel = VadTimelinePanel(self.method_specs)
        root_layout.addWidget(self.timeline_panel, stretch=1)
        root_layout.addStretch()
        self.setStyleSheet(
            get_drop_zone_stylesheet() +
            get_scrollbar_stylesheet() +
            self._local_stylesheet()
        )

    def update_from_other_tab(self, data):
        file_path = data.get("file_path")
        duration = data.get("duration")
        self._stop_parse_thread()
        if not file_path:
            self.current_file_path = ""
            self.current_duration = 0.0
            self.pending_approval = False
            self.file_info_label.setText("Waiting for broadcast from Time Slicer")
            self.parse_status_label.setText("Waiting for media broadcast")
            self.approve_button.hide()
            self.timeline_panel.clear_timeline()
            return

        self.current_file_path = file_path
        self.current_duration = float(duration or 0.0)
        display = add_zero_wide_char_to_str(file_path)
        self.file_info_label.setText(f"Loaded from Time Slicer: {display}")
        self.timeline_panel.reset_for_media(self.current_duration or 7200.0)

        if self.current_duration > APPROVAL_THRESHOLD_SEC:
            self.pending_approval = True
            self.parse_status_label.setText(
                "Long media detected (>10 min). Click Approve to start ffmpeg audio parsing."
            )
            self.approve_button.setEnabled(True)
            self.approve_button.show()
            self.timeline_panel.set_audio_status_message("Awaiting approval for audio parse")
        else:
            self.pending_approval = False
            self.approve_button.hide()
            self._start_audio_parse(auto_started=True)

    def _on_approve_clicked(self):
        if not self.current_file_path:
            return
        self.pending_approval = False
        self.approve_button.setEnabled(False)
        self._start_audio_parse(auto_started=False)

    def _start_audio_parse(self, auto_started: bool):
        if not self.current_file_path:
            return

        self.parse_generation += 1
        generation = self.parse_generation

        self.timeline_panel.set_audio_status_message("Parsing audio strength with ffmpeg...")
        if auto_started:
            self.parse_status_label.setText("Short media detected. Parsing audio automatically...")
        else:
            self.parse_status_label.setText("Approval received. Parsing audio strength...")

        self.approve_button.hide()

        self.parse_thread = AudioParseThread(
            generation=generation,
            media_path=self.current_file_path,
            duration_sec=self.current_duration or 7200.0,
            parent=self,
        )
        self.parse_thread.success.connect(self._on_parse_success)
        self.parse_thread.failed.connect(self._on_parse_failed)
        self.parse_thread.cancelled.connect(self._on_parse_cancelled)
        self.parse_thread.finished.connect(self.parse_thread.deleteLater)
        self.parse_thread.start()

    def _on_parse_success(self, generation: int, strength_series):
        if generation != self.parse_generation:
            return

        self.timeline_panel.set_audio_strength_data(strength_series)
        self.parse_status_label.setText(
            f"Audio parsed successfully: {len(strength_series)} strength samples at 50/sec"
        )
        self.parse_thread = None

    def _on_parse_failed(self, generation: int, error_message: str):
        if generation != self.parse_generation:
            return

        self.timeline_panel.set_audio_status_message("Audio parse failed")
        self.parse_status_label.setText(f"Audio parse failed: {error_message}")
        if self.current_duration > APPROVAL_THRESHOLD_SEC:
            self.pending_approval = True
            self.approve_button.setEnabled(True)
            self.approve_button.show()
        self.parse_thread = None

    def _on_parse_cancelled(self, generation: int):
        if generation != self.parse_generation:
            return

        self.timeline_panel.set_audio_status_message("Audio parse cancelled")
        self.parse_status_label.setText("Audio parse cancelled")
        if self.pending_approval and self.current_file_path:
            self.approve_button.setEnabled(True)
            self.approve_button.show()
        self.parse_thread = None

    def _stop_parse_thread(self):
        if self.parse_thread and self.parse_thread.isRunning():
            self.parse_generation += 1
            self.parse_thread.stop()
            self.parse_thread.wait(1000)
        self.parse_thread = None

    @staticmethod
    def _local_stylesheet():
        return """
            QFrame#vadExpNote {
                background-color: #f7f7f7;
                border: 1px solid #dddddd;
                border-radius: 4px;
            }
            QFrame#vadApprovalGate {
                background-color: #f7f7f7;
                border: 1px solid #dddddd;
                border-radius: 4px;
            }
            QFrame#vadMethodPanel {
                background-color: #ffffff;
                border: 1px solid #d7d7d7;
                border-radius: 6px;
            }
            QFrame#vadControlPanel {
                background-color: #f5f5f5;
                border: 1px solid #e2e2e2;
                border-radius: 4px;
            }
            QLabel#vadMethodTitle {
                font-size: 15px;
                font-weight: bold;
            }
            QScrollArea {
                background-color: #ffffff;
                border: 1px solid #e0e0e0;
            }
        """
