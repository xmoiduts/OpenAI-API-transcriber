from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QFrame, QHBoxLayout, QPushButton

from src.configuration_manager.configuration_manager import ConfigManager
from src.vad.coordinator import ParallelVadConfig
from src.vad.models import VadTimeRange
from .tab_interface import TabInterface
from .styles.style_manager import get_drop_zone_stylesheet, get_scrollbar_stylesheet
from .util.add_zero_wide_char_to_str import add_zero_wide_char_to_str
from .vad_exp.audio_parse_thread import AudioParseThread
from .vad_exp.timeline_widgets import VadInterval, VadMethodSpec, VadTimelinePanel
from src.vad.adapters import SileroVadEngine
from src.vad.service import VadApplicationService


APPROVAL_THRESHOLD_SEC = 10 * 60
SILERO_ENGINE_KEY = "silero"


class VADExpTab(TabInterface):
    """Experimental tab for comparing multiple future VAD implementations.

    For the current Silero-first wiring and extension notes, see
    `doc/vad-engine-silero-integration.md`.
    """

    def __init__(self):
        super().__init__("VAD Exp")
        self.current_file_path = ""
        self.current_duration = 0.0
        self.current_request_range = None
        self.pending_approval = False
        self.parse_generation = 0
        self.parse_thread = None
        self.vad_service = VadApplicationService([SileroVadEngine()])
        self.parallel_config = self._load_parallel_config()
        self.method_specs = [
            VadMethodSpec(
                method_key=SILERO_ENGINE_KEY,
                title="Silero VAD",
                accent_color="#4A90D9",
                description="Real speech regions from the first VAD engine slot.",
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
            QLabel("Current round: actual audio-strength tiles plus Silero VAD on the first lane")
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

        for row in self.timeline_panel.method_rows:
            row.send_slices.connect(self._on_row_send_slices)

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
            self.current_request_range = None
            self.pending_approval = False
            self.file_info_label.setText("Waiting for broadcast from Time Slicer")
            self.parse_status_label.setText("Waiting for media broadcast")
            self.approve_button.hide()
            self.timeline_panel.clear_timeline()
            return

        self.current_file_path = file_path
        self.current_duration = float(duration or 0.0)
        self.current_request_range = None
        display = add_zero_wide_char_to_str(file_path)
        self.file_info_label.setText(f"Loaded from Time Slicer: {display}")
        self.timeline_panel.reset_for_media(self.current_duration or 7200.0)

        if self.current_duration > APPROVAL_THRESHOLD_SEC:
            self.pending_approval = True
            self.parse_status_label.setText(
                "Long media detected (>10 min). Click Approve to start amplitude + Silero VAD analysis."
            )
            self.approve_button.setEnabled(True)
            self.approve_button.show()
            self.timeline_panel.set_audio_status_message("Awaiting approval for amplitude + Silero VAD")
            self._show_cached_vad_result()
        else:
            self.pending_approval = False
            self.approve_button.hide()
            self._show_cached_vad_result()
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

        self.request_analysis_range(
            start_sec=0.0,
            end_sec=self.current_duration or 7200.0,
            include_amplitude=True,
            include_vad=True,
            auto_started=auto_started,
        )

    def request_analysis_range(
        self,
        start_sec: float,
        end_sec: float,
        include_amplitude: bool,
        include_vad: bool,
        auto_started: bool = False,
    ):
        if not self.current_file_path:
            return

        self.parse_generation += 1
        generation = self.parse_generation
        self.current_request_range = VadTimeRange(start_sec, end_sec)

        request_label = self._describe_request(include_amplitude, include_vad)
        self.timeline_panel.set_audio_status_message(f"Running {request_label} analysis...")
        self.timeline_panel.set_processing_state(processed_ranges=[], active_ranges=[])
        if auto_started:
            self.parse_status_label.setText(f"Short media detected. Running {request_label} automatically...")
        else:
            self.parse_status_label.setText(f"Approval received. Running {request_label}...")

        self.approve_button.hide()

        self.parse_thread = AudioParseThread(
            generation=generation,
            media_path=self.current_file_path,
            duration_sec=self.current_duration or 7200.0,
            service=self.vad_service,
            start_sec=start_sec,
            end_sec=end_sec,
            include_amplitude=include_amplitude,
            include_vad=include_vad,
            engine_key=SILERO_ENGINE_KEY,
            parallel_config=self.parallel_config,
            engine_factory=SileroVadEngine,
            parent=self,
        )
        self.parse_thread.partial_update.connect(self._on_partial_update)
        self.parse_thread.success.connect(self._on_parse_success)
        self.parse_thread.failed.connect(self._on_parse_failed)
        self.parse_thread.cancelled.connect(self._on_parse_cancelled)
        self.parse_thread.finished.connect(self.parse_thread.deleteLater)
        self.parse_thread.start()

    def _on_partial_update(self, generation: int, analysis_output):
        if generation != self.parse_generation:
            return

        if analysis_output.amplitude_patch is not None:
            self.timeline_panel.apply_audio_strength_patch(
                analysis_output.amplitude_patch,
                peak_value=analysis_output.amplitude_peak,
            )
        elif analysis_output.amplitude_peak is not None:
            self.timeline_panel.set_audio_peak(analysis_output.amplitude_peak)

        if analysis_output.vad_result is not None:
            self.timeline_panel.set_method_vad_intervals(
                SILERO_ENGINE_KEY,
                self._build_vad_intervals(analysis_output.vad_result.speech_segments),
            )

        self.timeline_panel.set_processing_state(
            processed_ranges=analysis_output.processed_ranges,
            active_ranges=analysis_output.active_ranges,
        )
        if analysis_output.status_message:
            self.parse_status_label.setText(analysis_output.status_message)

    def _on_parse_success(self, generation: int, analysis_output):
        if generation != self.parse_generation:
            return

        if analysis_output.amplitude_series is not None:
            self.timeline_panel.set_audio_strength_data(
                analysis_output.amplitude_series,
                peak_value=analysis_output.amplitude_peak,
            )

        if analysis_output.vad_result is not None:
            self.timeline_panel.set_method_vad_intervals(
                SILERO_ENGINE_KEY,
                self._build_vad_intervals(analysis_output.vad_result.speech_segments),
            )

        if self.current_request_range is not None:
            self.timeline_panel.set_processing_state(
                processed_ranges=[self.current_request_range],
                active_ranges=[],
            )
        else:
            self.timeline_panel.clear_active_processing()

        strength_count = 0
        if analysis_output.amplitude_series is not None:
            strength_count = len(analysis_output.amplitude_series)

        segment_count = 0
        if analysis_output.vad_result is not None:
            segment_count = len(analysis_output.vad_result.speech_segments)

        self.parse_status_label.setText(
            f"{analysis_output.status_message}: {strength_count} strength samples, {segment_count} speech segments"
        )
        self.parse_thread = None

    def _on_parse_failed(self, generation: int, error_message: str):
        if generation != self.parse_generation:
            return

        self.timeline_panel.clear_active_processing()
        self.timeline_panel.set_audio_status_message("Analysis failed")
        self.parse_status_label.setText(f"Amplitude/VAD analysis failed: {error_message}")
        if self.current_duration > APPROVAL_THRESHOLD_SEC:
            self.pending_approval = True
            self.approve_button.setEnabled(True)
            self.approve_button.show()
        self.parse_thread = None

    def _on_parse_cancelled(self, generation: int):
        if generation != self.parse_generation:
            return

        self.timeline_panel.clear_active_processing()
        self.timeline_panel.set_audio_status_message("Analysis cancelled")
        self.parse_status_label.setText("Amplitude/VAD analysis cancelled")
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

    def _show_cached_vad_result(self):
        cached = self.vad_service.get_cached_result(self.current_file_path, SILERO_ENGINE_KEY)
        if cached is None:
            return
        self.timeline_panel.set_method_vad_intervals(
            SILERO_ENGINE_KEY,
            self._build_vad_intervals(cached.speech_segments),
        )

    @staticmethod
    def _build_vad_intervals(speech_segments):
        return [
            VadInterval(start_sec=segment.start_sec, end_sec=segment.end_sec, label="speech")
            for segment in speech_segments
        ]

    def _on_row_send_slices(self, slices: list):
        main_window = self._get_main_window()
        if main_window and hasattr(main_window, "push_slices_to_transcription"):
            main_window.push_slices_to_transcription(
                self.current_file_path,
                self.current_duration,
                slices,
            )

    def _get_main_window(self):
        parent = self.parent()
        while parent is not None:
            if hasattr(parent, "push_slices_to_transcription"):
                return parent
            parent = parent.parent()
        return None

    @staticmethod
    def _describe_request(include_amplitude: bool, include_vad: bool) -> str:
        if include_amplitude and include_vad:
            return "amplitude + Silero VAD"
        if include_amplitude:
            return "amplitude-only"
        return "Silero VAD-only"

    @staticmethod
    def _load_parallel_config() -> ParallelVadConfig:
        vad_config = ConfigManager().get_vad_config()
        return ParallelVadConfig(
            parallel_workers=int(vad_config.get("parallel_workers", 4)),
            slice_minutes=int(vad_config.get("slice_minutes", 2)),
            parallel_min_duration_seconds=int(vad_config.get("parallel_min_duration_seconds", 900)),
        )

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
