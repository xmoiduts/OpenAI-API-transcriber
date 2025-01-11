from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, 
                            QPushButton, QFileDialog, QTextBrowser, QProgressBar,  # 改为 QTextBrowser
                            QComboBox)
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, Qt
from .tab_interface import TabInterface
from .segment_bar import SegmentBar
from src.time_slicer.time_slicer import get_time_slices
from src.transcriber_core.transcriber import WhisperTranscriber
from .flying_message import show_flying_message
from .util.add_zero_wide_char_to_str import add_zero_wide_char_to_str
from .styles.style_manager import get_dropdown_stylesheet
import os
import sys
import subprocess

class TranscriptionNewTab(TabInterface):
    def __init__(self):
        super().__init__("Transcription New")
        self.transcriber = WhisperTranscriber()
        self.config = self._load_config()
        self.init_ui()
        self.file_path = None
        self.duration = None
        self.slices = None
        self.log_queue = []

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
        #   Transcribe button
        self.transcribe_button = QPushButton("Transcribe")
        self.transcribe_button.clicked.connect(self.start_transcription)
        self.transcribe_button.setEnabled(False) # Disable initially
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
        bottom_section.addWidget(self.stop_button)
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
            selected_model = self.model_selector.currentText()
            selected_provider = self.provider_selector.currentText()
            if selected_model in ["---not configured---"] or \
                selected_provider in ["---invalid model---"]:
                    show_flying_message(self, "Invalid model or provider selection")
                    return
            assert self.transcriber.set_model_and_provider(selected_model, selected_provider) is True

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

            self.stop_button.setEnabled(True)

        except Exception as e:
            import traceback
            error_message = f"Error during transcription: {str(e)}\n\nCall Stack:\n{traceback.format_exc()}"
            self.update_log(error_message)
            self.transcribe_button.setEnabled(True)

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
        """获取转录结果目录的路径，如果目录不存在则返回父目录"""
        if not self.file_path:
            return None
        
        try:
            # 从环境变量获取项目根目录
            project_root = os.environ.get('PROJECT_ROOT')
            if not project_root:
                self.update_log("Error: PROJECT_ROOT not set")
                return None
            
            # 获取文件名（不含扩展名）
            file_name_core = os.path.splitext(os.path.basename(self.file_path))[0]
            
            # 构建结果目录路径并规范化
            result_dir = os.path.normpath(os.path.join(
                project_root,
                "transcription_result",
                file_name_core
            ))
            
            # 检查目录是否存在，如果不存在则尝试返回父目录
            if not os.path.exists(result_dir):
                parent_dir = os.path.dirname(result_dir)
                if os.path.exists(parent_dir):
                    return parent_dir
                else:
                    self.update_log(f"Directory not found: {result_dir}")
                    return None
                    
            return result_dir
            
        except Exception as e:
            self.update_log(f"Error determining result directory: {str(e)}")
            return None

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

    def handle_link_click(self, url):
        action = url.toString()
        if action == 'open_dir':
            self.open_result_directory()
        elif action == 'open_vscode':
            self.open_in_vscode()

    def transcription_finished(self, success):
        if success:
            self.update_log("\nTranscription completed successfully B")
            self.update_log("Actions:")
            # 安全地断开旧的连接
            try:
                self.log_display.anchorClicked.disconnect(self.handle_link_click)
            except TypeError:  # 如果信号未连接，会抛出 TypeError
                pass
            
            self.log_display.insertHtml(" • <a href='open_dir'>Open Result Directory</a><br>")
            self.log_display.insertHtml(" • <a href='open_vscode'>Open in VSCode</a><br>")
            self.log_display.setReadOnly(True)
            self.log_display.anchorClicked.connect(self.handle_link_click)
            self.log_display.setOpenLinks(False)
            self.log_display.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextBrowserInteraction
            )
        else:
            self.update_log("Transcription failed")
        
        self.transcribe_button.setEnabled(True)
        self.progress_bar.hide()
        self.stop_button.setEnabled(False)

    def stop_transcription(self):
        if hasattr(self, 'transcription_thread'):
            self.transcription_thread.stop_requested = True
            self.stop_button.setEnabled(False)
            self.update_log("\nStopping transcription after current segment...")

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
        self.stop_requested = False
        assert len(self.slices) == len(self.actual_starts)

    def run(self):
        try:
            total_slices = len(self.slices)
            for i, (slice_start, duration) in enumerate(self.slices):
                if self.stop_requested:
                    self.log_signal.emit("\nTranscription stopped by user")
                    self.finished_signal.emit(False)
                    return

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

                # TODO: apply rate control here
                import time # delay 30 seconds before launching next transcribe request, for API throttling.
                time.sleep(30)
            
            self.finished_signal.emit(True)
        except Exception as e:
            self.segment_status_signal.emit(i, "error")
            self.log_signal.emit(f"Error during transcription: {str(e)}")
            self.finished_signal.emit(False)