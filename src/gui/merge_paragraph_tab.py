from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton, 
    QFileDialog, QApplication
)
from PyQt5.QtCore import Qt
from .tab_interface import TabInterface
from .styles.style_manager import get_drop_zone_stylesheet, get_button_stylesheet
from .flying_message import show_flying_message
from .util.add_zero_wide_char_to_str import add_zero_wide_char_to_str
import os
import glob
import json
import re
from pathlib import Path
from src.configuration_manager.configuration_manager import ConfigManager

class MergeParagraphTab(TabInterface):
    def __init__(self):
        super().__init__("Merge Paragraphs")
        self.target_directory = ""
        self.init_ui()
        self.setAcceptDrops(True)
        # Combine stylesheets
        self.setStyleSheet(get_button_stylesheet() + get_drop_zone_stylesheet())

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        self.drop_zone = QLabel("Drag a file or directory here")
        self.drop_zone.setAlignment(Qt.AlignCenter)
        self.drop_zone.setProperty("dropZone", True)
        self.drop_zone.setMinimumHeight(100)
        layout.addWidget(self.drop_zone)

        self.loaded_path_label = QLabel("Loaded path: ")
        self.loaded_path_label.setWordWrap(True)
        layout.addWidget(self.loaded_path_label)

        button_layout = QHBoxLayout()
        self.merge_button = QPushButton("Merge and Save to TXT")
        self.merge_button.clicked.connect(self.merge_and_save)
        self.placeholder_button = QPushButton("Placeholder")
        self.placeholder_button.setEnabled(False)

        button_layout.addWidget(self.merge_button)
        button_layout.addWidget(self.placeholder_button)
        layout.addLayout(button_layout)
        
        layout.addStretch()

    def update_from_other_tab(self, data):
        """Receive data from other tabs, specifically Time Slicer"""
        file_path = data.get("file_path")
        if file_path:
            # Calculate transcription result directory based on transcriber.py logic
            config_manager = ConfigManager()
            paths = config_manager.get_paths_config()
            result_dir = Path(paths.get('result_dir', './transcription_result'))
            
            # Get file stem (filename without extension)
            input_path = Path(file_path)
            file_stem = input_path.stem
            
            # The transcription results are stored in result_dir/file_stem/
            transcription_dir = result_dir / file_stem
            
            if transcription_dir.exists():
                self.target_directory = str(transcription_dir)
                display_path = add_zero_wide_char_to_str(self.target_directory)
                self.loaded_path_label.setText(f"Loaded path: {display_path}")
                self.drop_zone.setText(f"Auto-loaded: {file_stem} transcription results")
                show_flying_message(self, f"Auto-loaded transcription directory: {transcription_dir}")
            else:
                self.loaded_path_label.setText(f"Transcription directory not found: {add_zero_wide_char_to_str(str(transcription_dir))}")
                self.drop_zone.setText("Transcription directory not found")
                show_flying_message(self, f"Transcription directory does not exist: {transcription_dir}")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            self.drop_zone.setProperty("dragOver", True)
            self.drop_zone.style().unpolish(self.drop_zone)
            self.drop_zone.style().polish(self.drop_zone)
            self.drop_zone.setText("Drop to load")
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.drop_zone.setProperty("dragOver", False)
        self.drop_zone.style().unpolish(self.drop_zone)
        self.drop_zone.style().polish(self.drop_zone)
        self.drop_zone.setText("Drag a file or directory here")

    def dropEvent(self, event):
        self.dragLeaveEvent(event)
        urls = event.mimeData().urls()
        if urls and urls[0].isLocalFile():
            path = urls[0].toLocalFile()
            if os.path.isdir(path):
                self.target_directory = path
            elif os.path.isfile(path):
                self.target_directory = os.path.dirname(path)
            else:
                self.target_directory = ""

            if self.target_directory:
                self.loaded_path_label.setText(f"Loaded path: {add_zero_wide_char_to_str(self.target_directory)}")
                self.drop_zone.setText(f"Directory loaded: {os.path.basename(self.target_directory)}")
                show_flying_message(self, f"Loaded directory: {self.target_directory}")
            else:
                self.loaded_path_label.setText("Loaded path: ")
                show_flying_message(self, "Could not determine a valid directory.")


    def merge_and_save(self):
        if not self.target_directory:
            show_flying_message(self, "Please load a directory first.")
            return

        json_files = []
        # Correct regex based on transcriber.py naming pattern:
        # {file_stem}_ss{display_start}-t{duration}_cut_result.json
        # We want the main result files, not the _segments.json files
        pattern = re.compile(r".*_ss\d+-t\d+_cut_result\.json$")
        
        for f in os.listdir(self.target_directory):
            if pattern.match(f):
                json_files.append(os.path.join(self.target_directory, f))

        if not json_files:
            show_flying_message(self, "No transcription JSON files found in the directory.")
            return
        
        # Sort files based on the start time (ss number) in the filename
        def extract_start_time(filename):
            match = re.search(r"_ss(\d+)-t\d+_cut_result\.json$", filename)
            return int(match.group(1)) if match else 0
        
        json_files.sort(key=lambda x: extract_start_time(os.path.basename(x)))

        all_text = []
        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "text" in data:
                        all_text.append(data["text"])
            except Exception as e:
                show_flying_message(self, f"Error reading {os.path.basename(file_path)}: {e}")
        
        output_content = "\n\n".join(all_text)
        output_file_path = os.path.join(self.target_directory, "原文未分段.txt")

        try:
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write(output_content)
            show_flying_message(self, f"Successfully saved to {output_file_path}")
        except Exception as e:
            show_flying_message(self, f"Error saving file: {e}") 