from PyQt5.QtWidgets import QVBoxLayout, QLabel, QPushButton, QTextEdit, QApplication, QHBoxLayout
from PyQt5.QtCore import Qt
from .tab_interface import TabInterface
from .segment_bar import SegmentBar
from src.time_slicer.time_slicer import get_time_slices
import subprocess
import os
import sys
from .util.add_zero_wide_char_to_str import add_zero_wide_char_to_str

class TranscriptionTab(TabInterface):
    def __init__(self):
        super().__init__("Transcription")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.file_info_label = QLabel("No file selected")
        self.file_info_label.setWordWrap(True)
        layout.addWidget(self.file_info_label)

        self.segment_bar = SegmentBar(mode="transcription")
        layout.addWidget(self.segment_bar)

        self.transcribe_button = QPushButton("Quick Transcribe")
        self.transcribe_button.clicked.connect(self.start_transcription)
        self.transcribe_button.setEnabled(False)  # Disable initially
        layout.addWidget(self.transcribe_button)

        self.setLayout(layout)

    def update_from_other_tab(self, data):
        file_path = data.get("file_path")
        duration = data.get("duration")
        self.file_path, self.duration = file_path, duration
        slices = data.get("slices")
        if file_path and duration:
            display_path = add_zero_wide_char_to_str(file_path)
            self.file_info_label.setText(
                f"File: {display_path} | Duration: {duration:.2f}s")
            self.transcribe_button.setEnabled(True)  # Enable the button when a file is selected
        else:
            self.file_info_label.setText("No file selected")
            self.transcribe_button.setEnabled(False)  # Disable the button when no file is selected
        if file_path and duration:
            self.segment_bar.set_segments(slices)
        else:
            self.segment_bar.set_segments([])

    def start_transcription(self):
        file_path = self.file_path
        duration = float(self.duration)
        

        # 获取项目根目录
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

        # Set script's path relative to project root
        script_path = './transcribe_audio.sh'

        # Choose correct shell by OS
        if sys.platform == "win32":
            # Try Git Bash first on Windows
            bash_paths = [
                r"C:\Program Files\Git\bin\bash.exe",
                r"C:\Program Files (x86)\Git\bin\bash.exe",
                # more paths optionally...
            ]
            for bash_path in bash_paths:
                if os.path.exists(bash_path):
                    shell = [bash_path, "-c"]
                    break
            # Use cmd if no Git Bash
            else:
                shell = ["cmd", "/c"]
        # Use bash on non-Windows systems
        else:
            shell = ["bash", "-c"]

        # 构建完整的命令
        command = f"{script_path} -i \"{file_path}\" -s 0 -t {int(duration)} "
        full_command = shell + [command]

        try:
            self.transcribe_button.setEnabled(False)
            print("Executing command:", " ".join(full_command))
            process = subprocess.Popen(
                full_command, 
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, 
                encoding='utf-8', 
                cwd=project_root,
                bufsize=1,
                universal_newlines=True
            )
            
            # Clear previous log display if it exists
            if hasattr(self, 'log_display'):
                self.layout().removeWidget(self.log_display)
                self.log_display.deleteLater()
                self.log_display = None

            # Create a QTextEdit widget to display the log
            self.log_display = QTextEdit()
            self.log_display.setReadOnly(True)
            self.layout().addWidget(self.log_display)

            # Read and display output in real-time
            for line in process.stdout:
                self.log_display.append(line.strip())
                QApplication.processEvents()  # Ensure GUI updates

            return_code = process.wait()

            if return_code == 0:
                self.log_display.append("Transcription completed successfully A")
            else:
                self.log_display.append(f"Error during transcription. Return code: {return_code}")
        except Exception as e:
            self.log_display.append(f"Error executing transcription command: {e}")
        finally:
            self.transcribe_button.setEnabled(True)