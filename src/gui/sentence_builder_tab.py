"""
Sentence Builder Tab - AI-assisted sentence building from word-timestamp ASR results.
VSCode-like three-panel layout: File Tree | Workspace | Task Cards Sidebar

Layout:
- Left: File Tree Panel (existing)
- Middle: Workspace Panel (blank, reserved for Scintilla)
- Right: Task Cards Panel (replaces original Chat Sidebar)

Note: Original Chat Sidebar code is preserved in:
    src/gui/components/chat_sidebar_backup.py
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QSplitter,
    QTreeWidget, QTreeWidgetItem, QScrollArea, QLabel,
    QPlainTextEdit, QPushButton, QSizePolicy, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QEvent
from PyQt5.QtGui import QFont
from pathlib import Path
import sys
import re

from .tab_interface import TabInterface
from .styles.style_manager import get_sentence_builder_combined_stylesheet
from .components.model_selector import ModelSelectorWidget
from .components.task_card import MergeOverlapsCard, CutpointCard, AssembleCard
from .components.task_popup_window import TaskPopupWindow
from .flying_message import show_flying_message

# Add src to path for imports
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from chatbot_core import ChatCore
from chatbot_core.thinking_resolver import resolve_thinking
from sentence_builder.reverse_dedup import (
    find_time_reversals,
    get_reversal_contexts,
    get_reversal_segments,
    find_latest_transcription_result,
    parse_timestamp_file,
)
from sentence_builder.context_formatter import format_and_retime_context, format_with_source_labeling


class SentenceBuilderTab(TabInterface):
    """Main tab for AI-assisted sentence building."""
    
    def __init__(self):
        super().__init__("Sentence Builder")
        self.init_ui()
        
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create splitter for resizable panels
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Left: File Tree Panel
        self.file_tree_panel = FileTreePanel()
        self.file_tree_panel.setMinimumWidth(180)
        self.file_tree_panel.setMaximumWidth(350)
        self.splitter.addWidget(self.file_tree_panel)
        
        # Middle: Workspace Panel (blank, reserved for Scintilla)
        self.workspace_panel = WorkspacePanel()
        self.splitter.addWidget(self.workspace_panel)
        
        # Right: Task Cards Sidebar Panel (replaces Chat Sidebar)
        self.task_cards_panel = TaskCardsSidebarPanel()
        self.task_cards_panel.setMinimumWidth(300)
        self.task_cards_panel.setMaximumWidth(500)
        self.splitter.addWidget(self.task_cards_panel)
        
        # Set initial sizes (left: 200, middle: stretch, right: 380)
        self.splitter.setSizes([200, 500, 380])
        
        layout.addWidget(self.splitter)
        
        # Apply styles
        self.setStyleSheet(get_sentence_builder_combined_stylesheet())
        
    def update_from_other_tab(self, data):
        """Receive data from other tabs."""
        pass


class FileTreePanel(QFrame):
    """Left panel: File tree with hardcoded expanded folders."""
    
    fileClicked = pyqtSignal(str)  # Emits file path when clicked
    
    def __init__(self):
        super().__init__()
        self.setObjectName("fileTreePanel")
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QLabel("Files")
        header.setObjectName("panelHeader")
        header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setFixedHeight(32)
        layout.addWidget(header)
        
        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setObjectName("fileTree")
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree)
        
        # Populate with sample structure
        self._populate_sample_tree()
        
    def _populate_sample_tree(self):
        """Populate tree with sample file structure."""
        # Sample folder 1
        folder1 = QTreeWidgetItem(self.tree, ["transcription_result/"])
        folder1.setExpanded(True)
        QTreeWidgetItem(folder1, ["segment_001.json"])
        QTreeWidgetItem(folder1, ["segment_002.json"])
        QTreeWidgetItem(folder1, ["segment_003.json"])
        QTreeWidgetItem(folder1, ["merged_output.json"])
        
        # Sample folder 2
        folder2 = QTreeWidgetItem(self.tree, ["context-cards/"])
        folder2.setExpanded(True)
        QTreeWidgetItem(folder2, ["korone-pochi.yaml"])
        QTreeWidgetItem(folder2, ["nanahira.yaml"])
        
        # Sample folder 3
        folder3 = QTreeWidgetItem(self.tree, ["config/"])
        folder3.setExpanded(True)
        QTreeWidgetItem(folder3, ["config.yaml"])
        QTreeWidgetItem(folder3, ["api_endpoint"])
        
    def _on_item_clicked(self, item, column):
        """Handle item click - emit signal for files only."""
        # Check if it's a file (no children = leaf node)
        if item.childCount() == 0:
            # Build path from item hierarchy
            path_parts = []
            current = item
            while current:
                path_parts.insert(0, current.text(0))
                current = current.parent()
            full_path = "/".join(path_parts)
            self.fileClicked.emit(full_path)
            
    def set_directory(self, directory_path):
        """Set the directory to display (for future implementation)."""
        # TODO: Actually scan directory
        pass


class WorkspacePanel(QFrame):
    """Middle panel: Blank workspace placeholder (reserved for Scintilla)."""
    
    def __init__(self):
        super().__init__()
        self.setObjectName("workspacePanel")
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header with audio model selector
        header_frame = QFrame()
        header_frame.setObjectName("panelHeader")
        header_frame.setFixedHeight(40)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(8)
        
        header_label = QLabel("Workspace")
        header_label.setStyleSheet("color: #e0e0e0; font-weight: bold;")
        header_layout.addWidget(header_label)
        
        header_layout.addStretch()
        
        # Audio transcription model selector
        audio_label = QLabel("ASR Model:")
        audio_label.setStyleSheet("color: #888888; font-size: 11px;")
        header_layout.addWidget(audio_label)
        
        self.audio_model_selector = ModelSelectorWidget(
            applicable_task="audio-transcription",
            max_popup_height=350
        )
        self.audio_model_selector.selection_confirmed.connect(self._on_audio_model_selected)
        header_layout.addWidget(self.audio_model_selector)
        
        layout.addWidget(header_frame)
        
        # Blank content area
        content = QFrame()
        content.setObjectName("workspaceContent")
        content_layout = QVBoxLayout(content)
        
        placeholder = QLabel("Select a file to begin\n\n(Reserved for Scintilla editor)")
        placeholder.setObjectName("workspacePlaceholder")
        placeholder.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(placeholder)
        
        layout.addWidget(content)
    
    def _on_audio_model_selected(self, model: str, provider: str):
        """Handle audio model selection."""
        print(f"[WorkspacePanel] Audio model selected: {model} @ {provider}")


class TaskCardsSidebarPanel(QFrame):
    """Right panel: Scrollable task cards with model selector at bottom.
    
    Replaces the original ChatSidebarPanel.
    """
    
    def __init__(self):
        super().__init__()
        # Reuse existing SentenceBuilder/Chat sidebar styling (light theme + nice scrollbar)
        self.setObjectName("chatSidebarPanel")
        
        # ChatCore instance shared by all tasks
        self.chat_core = ChatCore(
            system_prompt="You are an expert at analyzing ASR transcription output and assembling coherent sentences."
        )
        
        # Track current transcription directory
        self._current_result_dir: Path = None
        self._word_timestamps_file: Path = None
        self._total_lines: int = 0
        
        # Track popup windows
        self._popup_windows: list = []
        
        self.init_ui()
        
        # Auto-detect transcription result on load
        self._auto_detect_result()

    def _create_isolated_chat_core(self) -> ChatCore:
        """
        Create a new ChatCore instance for a single task window.

        Rationale:
        - Avoid sharing a single ChatCore/ChatThread across multiple concurrent
          TaskPopupWindow workers (which can cause request/stream mix-ups).
        - Keep each task's prompt/history isolated so the LLM responds to the
          correct slice context.
        """
        system_prompt = self.chat_core.get_system_prompt()
        isolated = ChatCore(system_prompt=system_prompt)

        # Mirror the currently selected model/provider.
        model = self.chat_core.get_current_model()
        provider = self.chat_core.get_current_provider()
        if model and provider:
            isolated.set_model(model, provider)

        return isolated
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QLabel("Task Cards")
        header.setObjectName("panelHeader")
        header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setFixedHeight(32)
        layout.addWidget(header)
        
        # Status label
        self.status_label = QLabel("Auto-detecting transcription results...")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        # Keep this light; avoid hardcoding dark backgrounds here.
        self.status_label.setStyleSheet("color: #666666; font-size: 10px; padding: 4px 8px;")
        layout.addWidget(self.status_label)
        
        # Scrollable card area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # Reuse chatHistory scrollbar + background styles from get_sentence_builder_combined_stylesheet()
        scroll.setObjectName("chatHistory")
        
        # Card container
        self.card_container = QWidget()
        # Reuse chatHistoryContainer background
        self.card_container.setObjectName("chatHistoryContainer")
        card_layout = QVBoxLayout(self.card_container)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(12)
        
        # Create task cards
        self.merge_overlaps_card = MergeOverlapsCard()
        self.merge_overlaps_card.start_clicked.connect(self._on_merge_overlaps_start_v2)
        self.merge_overlaps_card.start_hovered.connect(self._on_start_hover)
        card_layout.addWidget(self.merge_overlaps_card)
        
        self.cutpoint_card = CutpointCard()
        self.cutpoint_card.start_clicked.connect(self._on_cutpoint_start)
        self.cutpoint_card.start_hovered.connect(self._on_start_hover)
        card_layout.addWidget(self.cutpoint_card)
        
        self.assemble_card = AssembleCard()
        self.assemble_card.start_clicked.connect(self._on_assemble_start)
        self.assemble_card.start_hovered.connect(self._on_start_hover)
        card_layout.addWidget(self.assemble_card)
        
        card_layout.addStretch()
        
        scroll.setWidget(self.card_container)
        layout.addWidget(scroll, 1)  # Stretch factor
        
        # Bottom control bar
        control_bar = QFrame()
        # Reuse the existing light control-bar styling
        control_bar.setObjectName("chatControlBar")
        control_bar.setFixedHeight(50)
        
        control_layout = QHBoxLayout(control_bar)
        control_layout.setContentsMargins(8, 8, 8, 8)
        control_layout.setSpacing(8)
        
        # Model selector
        self.model_selector = ModelSelectorWidget(
            applicable_task="text-chat",
            max_popup_height=400
        )
        self.model_selector.selection_confirmed.connect(self._on_model_selected)
        control_layout.addWidget(self.model_selector)
        
        control_layout.addStretch()
        
        # Settings button (placeholder)
        self.settings_button = QPushButton("⚙")
        self.settings_button.setObjectName("settingsButton")
        self.settings_button.setFixedSize(32, 32)
        self.settings_button.setToolTip("Settings (coming soon)")
        self.settings_button.setStyleSheet("""
            QPushButton#settingsButton {
                background-color: #e8e8e8;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                color: #333333;
                font-size: 14px;
            }
            QPushButton#settingsButton:hover {
                background-color: #d8d8d8;
            }
        """)
        control_layout.addWidget(self.settings_button)
        
        layout.addWidget(control_bar)
    
    def _auto_detect_result(self):
        """Auto-detect the latest transcription result directory."""
        result_dir = find_latest_transcription_result()
        if result_dir:
            self._set_result_directory(result_dir)
        else:
            self.status_label.setText("No transcription results found")
    
    def _set_result_directory(self, result_dir: Path):
        """Set the current result directory and update UI."""
        self._current_result_dir = result_dir
        self._word_timestamps_file = result_dir / 'merged_word_timestamps.csv'
        
        if self._word_timestamps_file.exists():
            # Count lines
            words = parse_timestamp_file(str(self._word_timestamps_file))
            self._total_lines = len(words)
            
            # Update status (truncate long names)
            name = result_dir.name
            if len(name) > 30:
                name = name[:27] + "..."
            self.status_label.setText(f"Loaded: {name} ({self._total_lines:,} entries)")
            
            # Update cutpoint card max lines
            self.cutpoint_card.set_max_lines(self._total_lines)
            
            # Update assemble card default ranges
            if self._total_lines > 0:
                ranges = []
                chunk_size = 3000
                for i in range(0, self._total_lines, chunk_size):
                    end = min(i + chunk_size, self._total_lines)
                    ranges.append((i + 1, end))
                self.assemble_card.set_line_ranges(ranges)
        else:
            self.status_label.setText(f"Warning: merged_word_timestamps.csv not found")
    
    def _on_start_hover(self, is_hovering: bool):
        """Handle Start button hover - highlight model selector."""
        if is_hovering:
            # Bold border with green color
            self.model_selector.trigger_button.setStyleSheet("""
                QPushButton#modelSelectorButton {
                    background-color: #ffffff;
                    color: #333333;
                    border: 3px solid #4CAF50;
                    border-radius: 6px;
                    padding: 6px 14px;
                    text-align: left;
                    font-size: 12px;
                    min-width: 180px;
                }
            """)
        else:
            # Normal border
            self.model_selector.trigger_button.setStyleSheet("""
                QPushButton#modelSelectorButton {
                    background-color: #ffffff;
                    color: #333333;
                    border: 1px solid #d0d0d0;
                    border-radius: 6px;
                    padding: 8px 16px;
                    text-align: left;
                    font-size: 12px;
                    min-width: 180px;
                }
                QPushButton#modelSelectorButton:hover {
                    background-color: #f7f7f7;
                    border-color: #b0b0b0;
                }
            """)
    
    def _on_model_selected(self, model: str, provider: str):
        """Handle model selection."""
        success = self.chat_core.set_model(model, provider)
        if success:
            show_flying_message(self, f"Model set: {model}")
            self._refresh_thinking_controls()
        else:
            show_flying_message(self, f"Failed to set model: {model}")

    def _refresh_thinking_controls(self):
        """
        Refresh per-task thinking selector options based on the selected model/provider.
        Hides/omits 'no' when scheme does not support truly disabling thinking.
        """
        cfg = self.chat_core.get_current_config()
        if not cfg:
            return

        try:
            # Each task card reads its own default, but we also constrain the options by scheme.
            tasks = [
                (self.merge_overlaps_card, "merge_overlaps"),
                (self.cutpoint_card, "cutpoint"),
                (self.assemble_card, "assemble-sentence"),
            ]
            for card, task_key in tasks:
                res = resolve_thinking(cfg, None, task_key=task_key)
                card.set_supported_thinking_levels(res.ui_supported_levels)
        except Exception as e:
            print(f"[SentenceBuilder] Warning: failed to refresh thinking controls: {e}")
    
    def _check_model_selected(self) -> bool:
        """Check if a model is selected."""
        model, provider = self.model_selector.get_current_selection()
        if not model or not provider:
            show_flying_message(self, "Please select a model first")
            return False
        
        if self.chat_core.get_current_model() != model:
            self.chat_core.set_model(model, provider)
        
        return True
    
    def _check_data_loaded(self) -> bool:
        """Check if transcription data is loaded."""
        if not self._word_timestamps_file or not self._word_timestamps_file.exists():
            show_flying_message(self, "No word timestamps file loaded")
            return False
        return True
    
    def _create_popup(self, task_name: str, line_range: tuple = None, needs_approval: bool = False, slice_info: str = None) -> TaskPopupWindow:
        """Create and configure a popup window with cascading position."""
        popup = TaskPopupWindow(task_name, line_range, needs_approval=needs_approval, slice_info=slice_info)
        # Use an isolated ChatCore per popup to make concurrent tasks safe.
        popup.set_chat_core(self._create_isolated_chat_core())
        self._popup_windows.append(popup)
        popup.destroyed.connect(lambda: self._popup_windows.remove(popup) if popup in self._popup_windows else None)
        
        # Apply cascading offset (like Windows)
        cascade_offset = 30  # pixels
        index = len(self._popup_windows) - 1
        base_x = 100
        base_y = 100
        popup.move(base_x + index * cascade_offset, base_y + index * cascade_offset)
        
        return popup
    
    # =========================================================================
    # Task Handlers
    # =========================================================================
    
    def _on_merge_overlaps_start(self):
        """Handle Merge Overlaps task start with intelligent slicing."""
        if not self._check_model_selected() or not self._check_data_loaded():
            return
        
        # Get configuration
        chars_per_slice = self.merge_overlaps_card.get_chars_per_slice()
        prompt_template = self.merge_overlaps_card.get_prompt()
        user_input = self.merge_overlaps_card.get_user_input()
        thinking_level = self.merge_overlaps_card.get_thinking_level()
        
        # Create initial popup for detection
        detection_popup = self._create_popup("Merge Overlaps - Detection")
        detection_popup.show()
        
        detection_popup.log("Finding time reversal / overlap regions...")
        
        reversals = find_time_reversals(str(self._word_timestamps_file))
        detection_popup.log(f"Found {len(reversals)} overlap region(s)")
        
        if not reversals:
            detection_popup.log("No overlaps found - nothing to process")
            return
        
        contexts = get_reversal_contexts(str(self._word_timestamps_file), reversals)
        
        # Build formatted context strings with char length tracking
        # Apply reformat and retime to compress context for LLM
        formatted_contexts = []
        for ctx in contexts:
            reversal = ctx.get("reversal")
            try:
                reversal_line = getattr(reversal, "reversal_line", "?")
                start_t = getattr(reversal, "reversal_start_time", None)
                end_t = getattr(reversal, "overlap_end_time", None)
            except Exception:
                reversal_line, start_t, end_t = "?", None, None

            time_range = ""
            if isinstance(start_t, (int, float)) and isinstance(end_t, (int, float)):
                time_range = f"{start_t:.2f}s - {end_t:.2f}s"
            elif isinstance(start_t, (int, float)):
                time_range = f"from {start_t:.2f}s"

            # Apply formatting and retiming to context
            raw_context = ctx.get('context_text', '').strip()
            reformatted_context, time_offset = format_and_retime_context(raw_context)
            
            # Build header with offset info
            offset_info = f" | Time offset: -{time_offset}s" if time_offset > 0 else ""
            formatted_ctx = (
                f"=== Overlap Region (reversal line {reversal_line}) ===\n"
                f"Time: {time_range}{offset_info}\n"
                f"{reformatted_context}\n"
            )
            formatted_contexts.append(formatted_ctx)
        
        # Slice contexts into groups based on char limit
        slices = []
        current_slice = []
        current_chars = 0
        
        for i, ctx_text in enumerate(formatted_contexts):
            ctx_len = len(ctx_text)
            
            # If adding this context exceeds limit and we already have some contexts, start new slice
            if current_chars + ctx_len > chars_per_slice and current_slice:
                slices.append(current_slice)
                current_slice = []
                current_chars = 0
            
            current_slice.append((i, ctx_text))
            current_chars += ctx_len
        
        # Add remaining contexts
        if current_slice:
            slices.append(current_slice)
        
        detection_popup.log(f"Split into {len(slices)} slice(s) (max {chars_per_slice} chars per slice)")
        detection_popup.log(f"Creating {len(slices)} parallel task windows...")
        detection_popup.close()
        
        # Create popup for each slice
        for slice_idx, slice_contexts in enumerate(slices):
            slice_num = slice_idx + 1
            total_slices = len(slices)
            context_indices = [idx for idx, _ in slice_contexts]
            
            slice_info = f"Slice {slice_num}/{total_slices} (overlaps {context_indices[0]+1}-{context_indices[-1]+1})"
            needs_approval = slice_idx > 0  # First slice auto-approved, rest need approval
            
            popup = self._create_popup(
                "Merge Overlaps",
                needs_approval=needs_approval,
                slice_info=slice_info
            )
            popup.show()
            
            # Build context text for this slice
            context_text = "\n".join([ctx_text for _, ctx_text in slice_contexts])
            popup.set_context(context_text)
            
            # Build prompt
            prompt = prompt_template.replace("{user_input}", user_input or "None")
            prompt = prompt.replace("{context}", context_text)
            
            popup.log(f"Slice {slice_num}/{total_slices}")
            popup.log(f"Processing {len(slice_contexts)} overlap region(s)")
            popup.log(f"Overlap indices: {[idx+1 for idx in context_indices]}")
            popup.log(f"Context length: {len(context_text)} chars")
            popup.log(f"Prompt length: {len(prompt)} chars")
            
            if needs_approval:
                popup.log("⚠️ Waiting for manual approval to proceed...")
            else:
                popup.log("✓ Auto-approved (first slice)")
            
            # Execute prompt (will wait for approval if needed)
            popup.execute_prompt(
                prompt,
                thinking_level=thinking_level,
                task_key="merge_overlaps",
            )
    
    def _on_merge_overlaps_start_v2(self):
        """Handle Merge Overlaps task with source-labeled formatting (V2).
        
        New approach: Instead of concatenating overlapping segments with time reversal,
        merge them by time-sorting and labeling source (A/B).
        """
        if not self._check_model_selected() or not self._check_data_loaded():
            return
        
        # Get configuration
        chars_per_slice = self.merge_overlaps_card.get_chars_per_slice()
        prompt_template = self.merge_overlaps_card.get_prompt()
        user_input = self.merge_overlaps_card.get_user_input()
        thinking_level = self.merge_overlaps_card.get_thinking_level()
        
        # Create initial popup for detection
        detection_popup = self._create_popup("Merge Overlaps V2 - Detection")
        detection_popup.show()
        
        detection_popup.log("Finding time reversal / overlap regions...")
        
        reversals = find_time_reversals(str(self._word_timestamps_file))
        detection_popup.log(f"Found {len(reversals)} overlap region(s)")
        
        if not reversals:
            detection_popup.log("No overlaps found - nothing to process")
            return
        
        # Get segments with A/B separation
        segments = get_reversal_segments(str(self._word_timestamps_file), reversals)
        
        # Build formatted context strings with source labeling
        # Also collect line mappings for response conversion
        formatted_contexts = []
        context_line_mappings = []  # One mapping dict per context
        
        for seg in segments:
            reversal = seg.get("reversal")
            segment_a = seg.get("segment_a", [])
            segment_b = seg.get("segment_b", [])
            reversal_time = seg.get("reversal_time", 0.0)
            
            try:
                reversal_line = getattr(reversal, "reversal_line", "?")
                start_t = getattr(reversal, "reversal_start_time", None)
                end_t = getattr(reversal, "overlap_end_time", None)
            except Exception:
                reversal_line, start_t, end_t = "?", None, None
            
            time_range = ""
            if isinstance(start_t, (int, float)) and isinstance(end_t, (int, float)):
                time_range = f"{start_t:.2f}s - {end_t:.2f}s"
            elif isinstance(start_t, (int, float)):
                time_range = f"from {start_t:.2f}s"
            
            # Apply source-labeled formatting
            reformatted_context, time_offset = format_with_source_labeling(
                segment_a, segment_b, reversal_time
            )
            
            # Build line mapping for this context (for response conversion)
            from sentence_builder.response_converter import parse_context_to_line_mapping
            line_mapping = parse_context_to_line_mapping(reformatted_context, time_offset)
            context_line_mappings.append(line_mapping)
            
            # Build header with offset info
            offset_info = f" | Time offset: -{time_offset}s" if time_offset > 0 else ""
            formatted_ctx = (
                f"=== Overlap Region (reversal line {reversal_line}) ===\n"
                f"Time: {time_range}{offset_info}\n"
                f"{reformatted_context}\n"
            )
            formatted_contexts.append(formatted_ctx)
        
        # Slice contexts into groups based on char limit
        # Also group corresponding line mappings
        slices = []
        current_slice = []
        current_chars = 0
        
        for i, ctx_text in enumerate(formatted_contexts):
            ctx_len = len(ctx_text)
            
            # If adding this context exceeds limit and we already have some contexts, start new slice
            if current_chars + ctx_len > chars_per_slice and current_slice:
                slices.append(current_slice)
                current_slice = []
                current_chars = 0
            
            # Store (index, context_text, line_mapping)
            current_slice.append((i, ctx_text, context_line_mappings[i]))
            current_chars += ctx_len
        
        # Add remaining contexts
        if current_slice:
            slices.append(current_slice)
        
        detection_popup.log(f"Split into {len(slices)} slice(s) (max {chars_per_slice} chars per slice)")
        detection_popup.log(f"Creating {len(slices)} parallel task windows...")
        detection_popup.close()
        
        # Create popup for each slice
        for slice_idx, slice_contexts in enumerate(slices):
            slice_num = slice_idx + 1
            total_slices = len(slices)
            context_indices = [idx for idx, _, _ in slice_contexts]
            
            slice_info = f"V2-Slice {slice_num}/{total_slices} (overlaps {context_indices[0]+1}-{context_indices[-1]+1})"
            needs_approval = slice_idx > 0  # First slice auto-approved, rest need approval
            
            popup = self._create_popup(
                "Merge Overlaps V2",
                needs_approval=needs_approval,
                slice_info=slice_info
            )
            popup.show()
            
            # Build context text for this slice
            context_text = "\n".join([ctx_text for _, ctx_text, _ in slice_contexts])
            popup.set_context(context_text)
            
            # Group line mappings by offset (to handle multiple regions with same line numbers)
            # Structure: {offset: {line_num: (start, end, word)}}
            offset_grouped_mappings = {}
            for _, ctx_text, line_mapping in slice_contexts:
                # Extract offset from context header
                offset_match = re.search(r'Time offset:\s*-(\d+)s', ctx_text)
                if offset_match:
                    offset = int(offset_match.group(1))
                    if offset not in offset_grouped_mappings:
                        offset_grouped_mappings[offset] = {}
                    offset_grouped_mappings[offset].update(line_mapping)
            popup.set_line_mapping(offset_grouped_mappings)
            
            # Build prompt
            prompt = prompt_template.replace("{user_input}", user_input or "None")
            prompt = prompt.replace("{context}", context_text)
            
            popup.log(f"V2-Slice {slice_num}/{total_slices}")
            popup.log(f"Processing {len(slice_contexts)} overlap region(s)")
            popup.log(f"Overlap indices: {[idx+1 for idx in context_indices]}")
            popup.log(f"Context length: {len(context_text)} chars")
            popup.log(f"Prompt length: {len(prompt)} chars")
            
            if needs_approval:
                popup.log("⚠️ Waiting for manual approval to proceed...")
            else:
                popup.log("✓ Auto-approved (first slice)")
            
            # Execute prompt (will wait for approval if needed)
            popup.execute_prompt(
                prompt,
                thinking_level=thinking_level,
                task_key="merge_overlaps",
            )
    
    def _on_cutpoint_start(self):
        """Handle Cutpoint task start."""
        if not self._check_model_selected() or not self._check_data_loaded():
            return

        # ---------------------------------------------------------------------
        # Plan cutpoints first (detection/planning window)
        # ---------------------------------------------------------------------
        planning_popup = self._create_popup("Cutpoint - Planning")
        planning_popup.show()

        lines_per_segment = self.cutpoint_card.get_lines_per_segment()
        planning_popup.log(f"Lines per segment: {lines_per_segment}")
        planning_popup.log(f"Total lines: {self._total_lines}")

        cutpoints = list(range(lines_per_segment, self._total_lines, lines_per_segment))
        planning_popup.log(f"Planned cutpoints: {cutpoints}")

        if not cutpoints:
            planning_popup.log("File too short for cutpoints")
            return

        # Parse once and reuse for all windows
        words = parse_timestamp_file(str(self._word_timestamps_file))
        prompt_template = self.cutpoint_card.get_prompt()
        user_input = self.cutpoint_card.get_user_input()
        thinking_level = self.cutpoint_card.get_thinking_level()

        planning_popup.log(f"Creating {len(cutpoints)} parallel task windows...")
        planning_popup.close()

        # ---------------------------------------------------------------------
        # One send-ctx -> one popup window, with approval gate
        # ---------------------------------------------------------------------
        total = len(cutpoints)
        for ctx_idx, cutpoint in enumerate(cutpoints):
            ctx_num = ctx_idx + 1
            needs_approval = ctx_idx > 0  # First ctx auto-approved, rest need approval

            # Cutpoint is a 1-based line number in the timestamp file.
            # Convert to 0-based list index for slicing.
            center_idx = max(0, int(cutpoint) - 1)
            start_idx = max(0, center_idx - 50)
            end_idx = min(len(words), center_idx + 50)

            slice_info = f"{ctx_num}/{total} (line {cutpoint})"
            popup = self._create_popup("Cutpoint", needs_approval=needs_approval, slice_info=slice_info)
            popup.show()

            if center_idx >= len(words):
                popup.log(f"Cutpoint line {cutpoint} out of range for file (len={len(words)}). Skipping.")
                continue

            context_lines = []
            for i in range(start_idx, end_idx):
                start, end, word, line_num = words[i]

                # Normalize word: only quote spaces, strip quotes from others
                word_text = str(word)
                if word_text == "" or word_text.strip() == "":
                    word_text = '" "'

                # Compress consecutive times: if end == next start, show "~"
                end_str = f"{end:.2f}"
                if i < len(words) - 1:
                    next_start = words[i + 1][0]
                    if abs(end - next_start) < 0.001:
                        end_str = "~"

                marker = " // <- PROPOSED CUTPOINT" if line_num == cutpoint else ""
                # Desired format:
                # line_num start end_or_~ word_text // optional comment
                context_lines.append(f"{line_num} {start:.2f} {end_str} {word_text}{marker}")

            context_text = "\n".join(context_lines)
            popup.set_context(context_text)

            prompt = prompt_template.replace("{user_input}", user_input or "None")
            prompt = prompt.replace("{lines_per_segment}", str(lines_per_segment))
            prompt = prompt.replace("{context}", context_text)

            popup.log(f"Cutpoint {ctx_num}/{total}")
            popup.log(f"Proposed cutpoint line: {cutpoint}")
            popup.log(f"Context length: {len(context_text)} chars")
            popup.log(f"Prompt length: {len(prompt)} chars")

            if needs_approval:
                popup.log("⚠️ Waiting for manual approval to proceed...")
            else:
                popup.log("✓ Auto-approved (first ctx)")

            popup.execute_prompt(
                prompt,
                thinking_level=thinking_level,
                task_key="cutpoint",
            )

            QApplication.processEvents()
    
    def _on_assemble_start(self):
        """Handle Assemble Sentence task start."""
        if not self._check_model_selected() or not self._check_data_loaded():
            return
        
        line_ranges = self.assemble_card.get_line_ranges()
        
        if not line_ranges:
            show_flying_message(self, "No line ranges defined")
            return
        
        words = parse_timestamp_file(str(self._word_timestamps_file))
        
        for start_line, end_line in line_ranges:
            popup = self._create_popup("Assemble Sentence", (start_line, end_line))
            popup.show()
            
            popup.log(f"Processing lines {start_line} to {end_line}")
            
            context_lines = []
            for start, end, word, line_num in words:
                if start_line <= line_num <= end_line:
                    context_lines.append(f"{start:.2f} {end:.2f} \"{word}\"")
            
            if not context_lines:
                popup.log("No data in specified range")
                continue
            
            context_text = "\n".join(context_lines)
            popup.set_context(context_text)
            
            prompt_template = self.assemble_card.get_prompt()
            user_input = self.assemble_card.get_user_input()
            
            prompt = prompt_template.replace("{user_input}", user_input or "None")
            prompt = prompt.replace("{start_line}", str(start_line))
            prompt = prompt.replace("{end_line}", str(end_line))
            prompt = prompt.replace("{context}", context_text)
            
            popup.log(f"Sending prompt ({len(prompt)} chars) to LLM...")
            popup.execute_prompt(
                prompt,
                thinking_level=self.assemble_card.get_thinking_level(),
                task_key="assemble-sentence",
            )
            
            QApplication.processEvents()
