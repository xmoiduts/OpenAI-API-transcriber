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
from pathlib import Path
from src.configuration_manager.configuration_manager import ConfigManager
from src.util.filename_sanitizer import FilenameSanitizer
from src.hear_result_merger.merge_json import merge_and_save
from src.asr_postprocess.core import (
    merge_text_to_txt,
    convert_raw_json_to_csv,
    convert_merged_json_to_csv,
    convert_merged_json_to_delta_csv,
)


class ASRPostprocessTab(TabInterface):
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

        # Mode 1: no-timestamp postprocessing
        mode1_title = QLabel("Mode 1: no-timestamp postprocessing")
        mode1_title.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px;")
        layout.addWidget(mode1_title)
        
        button_layout_1 = QHBoxLayout()
        self.merge_button = QPushButton("Merge and Save to TXT")
        self.merge_button.clicked.connect(self.on_merge_and_save)
        self.word_timestamp_button = QPushButton("Convert to Word Timestamp CSV")
        self.word_timestamp_button.clicked.connect(self.on_convert_to_word_timestamp_csv)

        button_layout_1.addWidget(self.merge_button)
        button_layout_1.addWidget(self.word_timestamp_button)
        layout.addLayout(button_layout_1)
        
        # Separator line
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.HLine)
        separator1.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator1)
        
        # Mode 2: word-timestamp, offset
        mode2_title = QLabel("Mode 2: word-timestamp, offset")
        mode2_subtitle = QLabel("Format: {1145.14} {1145.28} — word start and end time as absolute offsets")
        mode2_title.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px;")
        mode2_subtitle.setStyleSheet("color: gray; font-size: 11px; margin-bottom: 5px;")
        layout.addWidget(mode2_title)
        layout.addWidget(mode2_subtitle)
        
        button_layout_2 = QHBoxLayout()
        self.merge_json_button = QPushButton("Merge Whisper JSON with Duplication, Keep Punctuations")
        self.merge_json_button.clicked.connect(self.on_merge_whisper_json)
        self.merged_to_csv_button = QPushButton("Convert Merged JSON to Word Timestamp CSV")
        self.merged_to_csv_button.clicked.connect(self.on_convert_merged_json_to_csv)

        button_layout_2.addWidget(self.merge_json_button)
        button_layout_2.addWidget(self.merged_to_csv_button)
        layout.addLayout(button_layout_2)
        
        # Separator line
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.HLine)
        separator2.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator2)
        
        # Mode 3: word-timestamp, delta (placeholder)
        mode3_title = QLabel("Mode 3: word-timestamp, delta")
        mode3_subtitle = QLabel("Format: 114514 +14 — word start time and duration delta in centi-seconds")
        mode3_title.setStyleSheet("font-weight: bold; font-size: 14px; margin-top: 10px;")
        mode3_subtitle.setStyleSheet("color: gray; font-size: 11px; margin-bottom: 5px;")
        layout.addWidget(mode3_title)
        layout.addWidget(mode3_subtitle)
        
        button_layout_3 = QHBoxLayout()
        self.convert_to_delta_csv_button = QPushButton("Convert Merged JSON to Delta CSV")
        self.convert_to_delta_csv_button.clicked.connect(self.on_convert_merged_json_to_delta_csv)
        
        button_layout_3.addWidget(self.convert_to_delta_csv_button)
        layout.addLayout(button_layout_3)
        
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

    # -------------------------------------------------------------------------
    # Button handlers - thin wrappers around core functions
    # -------------------------------------------------------------------------

    def on_merge_and_save(self):
        """Handler for 'Merge and Save to TXT' button."""
        if not self.target_directory:
            show_flying_message(self, "Please load a directory first.")
            return

        try:
            output_file = merge_text_to_txt(self.target_directory)
            show_flying_message(self, f"Successfully saved to {output_file}")
        except Exception as e:
            show_flying_message(self, f"Error: {e}")

    def on_convert_to_word_timestamp_csv(self):
        """Handler for 'Convert to Word Timestamp CSV' button."""
        if not self.target_directory:
            show_flying_message(self, "Please load a directory first.")
            return

        try:
            output_file = convert_raw_json_to_csv(self.target_directory)
            show_flying_message(self, f"Successfully saved to {output_file}")
        except Exception as e:
            show_flying_message(self, f"Error: {e}")

    def on_merge_whisper_json(self):
        """Handler for 'Merge Whisper JSON' button."""
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

    def on_convert_merged_json_to_csv(self):
        """Handler for 'Convert Merged JSON to Word Timestamp CSV' button."""
        if not self.target_directory:
            show_flying_message(self, "Please load a directory first.")
            return

        try:
            output_file = convert_merged_json_to_csv(self.target_directory)
            show_flying_message(self, f"Successfully saved to {output_file}")
        except Exception as e:
            show_flying_message(self, f"Error: {e}")
            import traceback
            traceback.print_exc()

    def on_convert_merged_json_to_delta_csv(self):
        """Handler for 'Convert Merged JSON to Delta CSV' button (Mode 3)."""
        if not self.target_directory:
            show_flying_message(self, "Please load a directory first.")
            return

        try:
            output_file = convert_merged_json_to_delta_csv(self.target_directory)
            show_flying_message(self, f"Successfully saved to {output_file}")
        except Exception as e:
            show_flying_message(self, f"Error: {e}")
            import traceback
            traceback.print_exc()

