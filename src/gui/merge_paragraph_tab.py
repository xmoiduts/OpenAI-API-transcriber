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
from src.util.filename_sanitizer import FilenameSanitizer
from src.hear_result_merger.merge_json import merge_and_save

class MergeParagraphTab(TabInterface):
    def __init__(self):
        super().__init__("ASR post process")
        self.target_directory = ""
        self.init_ui()
        self.setAcceptDrops(True)
        # Combine stylesheets
        self.setStyleSheet(get_button_stylesheet() + get_drop_zone_stylesheet())
        
        # Initialize filename sanitizer (same as transcriber.py)
        config_manager = ConfigManager()
        paths = config_manager.get_paths_config()
        result_dir = Path(paths.get('result_dir', './transcription_result'))
        self.filename_sanitizer = FilenameSanitizer(result_dir)

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

        # First row of buttons
        button_layout_1 = QHBoxLayout()
        self.merge_button = QPushButton("Merge and Save to TXT")
        self.merge_button.clicked.connect(self.merge_and_save)
        self.word_timestamp_button = QPushButton("Convert to Word Timestamp CSV")
        self.word_timestamp_button.clicked.connect(self.convert_to_word_timestamp_csv)

        button_layout_1.addWidget(self.merge_button)
        button_layout_1.addWidget(self.word_timestamp_button)
        layout.addLayout(button_layout_1)
        
        # Second row of buttons
        button_layout_2 = QHBoxLayout()
        self.merge_json_button = QPushButton("Merge Whisper JSON with Duplication, Keep Punctuations")
        self.merge_json_button.clicked.connect(self.merge_whisper_json)
        self.merged_to_csv_button = QPushButton("Convert Merged JSON to Word Timestamp CSV")
        self.merged_to_csv_button.clicked.connect(self.convert_merged_json_to_csv)

        button_layout_2.addWidget(self.merge_json_button)
        button_layout_2.addWidget(self.merged_to_csv_button)
        layout.addLayout(button_layout_2)
        
        layout.addStretch()

    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename using the same logic as transcriber.py.
        This ensures we can find the correct result directory.
        """
        return self.filename_sanitizer.sanitize(filename)

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
            
            # IMPORTANT: Use sanitized filename (same as transcriber.py)
            safe_file_stem = self._sanitize_filename(file_stem)
            
            # The transcription results are stored in result_dir/safe_file_stem/
            transcription_dir = result_dir / safe_file_stem
            
            if transcription_dir.exists():
                self.target_directory = str(transcription_dir)
                display_path = add_zero_wide_char_to_str(self.target_directory)
                self.loaded_path_label.setText(f"Loaded path: {display_path}")
                self.drop_zone.setText(f"Auto-loaded: {safe_file_stem} transcription results")
                show_flying_message(self, f"Auto-loaded transcription directory: {transcription_dir}")
            else:
                self.loaded_path_label.setText(f"Transcription directory not found: {add_zero_wide_char_to_str(str(transcription_dir))}\n\nDrag any file from the folder to load it")
                self.drop_zone.setText("Directory not found - drag any file to load its folder")
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

    def convert_to_word_timestamp_csv(self):
        """
        Convert word-level timestamps from all _cut_result.json files to a single CSV.
        CSV format: start end word (with start/end rounded to 2 decimal places)
        """
        if not self.target_directory:
            show_flying_message(self, "Please load a directory first.")
            return

        json_files = []
        # Find all _cut_result.json files
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

        # Collect all words from all JSON files
        all_rows = []
        for file_path in json_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if "words" in data and isinstance(data["words"], list):
                        for word_entry in data["words"]:
                            start = word_entry.get("start", 0)
                            end = word_entry.get("end", 0)
                            word = word_entry.get("word", "")
                            
                            # Format start and end to 2 decimal places
                            start_str = f"{start:.2f}"
                            end_str = f"{end:.2f}"
                            
                            # Escape word by wrapping in quotes
                            # Use double quotes and escape any quotes inside the word
                            word_escaped = word.replace('"', '""')
                            
                            # Create CSV row: start end word
                            row = f'{start_str} {end_str} "{word_escaped}"'
                            all_rows.append(row)
            except Exception as e:
                show_flying_message(self, f"Error reading {os.path.basename(file_path)}: {e}")
                return
        
        if not all_rows:
            show_flying_message(self, "No word-level timestamps found in the JSON files.")
            return
        
        # Write to CSV file
        output_file_path = os.path.join(self.target_directory, "word_timestamps.csv")
        
        try:
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(all_rows))
            show_flying_message(self, f"Successfully saved {len(all_rows)} word timestamps to {output_file_path}")
        except Exception as e:
            show_flying_message(self, f"Error saving CSV file: {e}")

    def merge_whisper_json(self):
        """
        Merge Whisper JSON files with duplication, keeping punctuations.
        Uses the merge_json module with dedup_method="none".
        """
        if not self.target_directory:
            show_flying_message(self, "Please load a directory first.")
            return

        try:
            # Call merge_and_save with dedup_method="none" to keep duplications
            output_file = merge_and_save(self.target_directory, dedup_method="none")
            show_flying_message(self, f"Successfully merged JSON files to {output_file}")
        except Exception as e:
            show_flying_message(self, f"Error merging JSON files: {e}")
            import traceback
            traceback.print_exc()

    def convert_merged_json_to_csv(self):
        """
        Convert the merged JSON file to word timestamp CSV.
        Similar to convert_to_word_timestamp_csv but reads from the merged JSON file.
        """
        if not self.target_directory:
            show_flying_message(self, "Please load a directory first.")
            return

        # Find the merged JSON file
        dir_name = os.path.basename(self.target_directory)
        merged_json_path = os.path.join(self.target_directory, f"merged_{dir_name}.json")
        
        if not os.path.exists(merged_json_path):
            show_flying_message(self, f"Merged JSON file not found: {merged_json_path}\nPlease run 'Merge Whisper JSON' first.")
            return

        try:
            with open(merged_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if "words" not in data or not isinstance(data["words"], list):
                show_flying_message(self, "No words found in merged JSON file.")
                return
            
            # Process words - the merged JSON has words as tuples: (start, end, word, [optional "punctuation"])
            all_rows = []
            for word_entry in data["words"]:
                if len(word_entry) >= 3:
                    start_time = word_entry[0]
                    end_time = word_entry[1]
                    word = word_entry[2]
                    
                    # Format timestamps to 2 decimal places
                    start_str = f"{start_time:.2f}"
                    end_str = f"{end_time:.2f}"
                    
                    # Escape word by wrapping in quotes
                    word_escaped = word.replace('"', '""')
                    
                    # Create CSV row: start end word
                    row = f'{start_str} {end_str} "{word_escaped}"'
                    all_rows.append(row)
            
            if not all_rows:
                show_flying_message(self, "No word timestamps found in merged JSON.")
                return
            
            # Write to CSV file
            output_file_path = os.path.join(self.target_directory, "merged_word_timestamps.csv")
            
            with open(output_file_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(all_rows))
            show_flying_message(self, f"Successfully saved {len(all_rows)} word timestamps to {output_file_path}")
        except Exception as e:
            show_flying_message(self, f"Error converting merged JSON to CSV: {e}")
            import traceback
            traceback.print_exc() 