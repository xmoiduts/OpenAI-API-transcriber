"""
Sentence Builder Tab - AI-assisted sentence building from word-timestamp ASR results.
VSCode-like three-panel layout: File Tree | Workspace | AI Chat Sidebar

Now integrated with ChatCore for multi-vendor LLM support (OpenAI, Claude, Gemini).
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QSplitter,
    QTreeWidget, QTreeWidgetItem, QScrollArea, QLabel,
    QPlainTextEdit, QPushButton, QSizePolicy, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QFont

from .tab_interface import TabInterface
from .styles.style_manager import get_sentence_builder_combined_stylesheet
from .components.model_selector import ModelSelectorWidget

# Import ChatCore
import sys
from pathlib import Path
# Add src to path for imports
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from chatbot_core import ChatCore


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
        
        # Middle: Workspace Panel (blank)
        self.workspace_panel = WorkspacePanel()
        self.splitter.addWidget(self.workspace_panel)
        
        # Right: Chat Sidebar Panel
        self.chat_sidebar = ChatSidebarPanel()
        self.chat_sidebar.setMinimumWidth(300)
        self.chat_sidebar.setMaximumWidth(500)
        self.splitter.addWidget(self.chat_sidebar)
        
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
    """Middle panel: Blank workspace placeholder."""
    
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
        
        placeholder = QLabel("Select a file to begin")
        placeholder.setObjectName("workspacePlaceholder")
        placeholder.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(placeholder)
        
        layout.addWidget(content)
    
    def _on_audio_model_selected(self, model: str, provider: str):
        """Handle audio model selection."""
        print(f"[WorkspacePanel] Audio model selected: {model} @ {provider}")


class ChatWorker(QThread):
    """Worker thread for async chat operations."""
    
    chunk_received = pyqtSignal(str)
    response_complete = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, chat_core: ChatCore, message: str):
        super().__init__()
        self.chat_core = chat_core
        self.message = message
        self._stop_requested = False
    
    def run(self):
        """Execute chat request in background thread."""
        try:
            full_response = ""
            
            # Use streaming
            gen = self.chat_core.send_stream(self.message)
            
            try:
                while not self._stop_requested:
                    chunk = next(gen)
                    full_response += chunk
                    self.chunk_received.emit(chunk)
            except StopIteration as e:
                # Generator finished, e.value contains the return value
                if e.value:
                    full_response = e.value
            
            if not self._stop_requested:
                self.response_complete.emit(full_response)
                
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def request_stop(self):
        """Request the worker to stop."""
        self._stop_requested = True


class ChatSidebarPanel(QFrame):
    """Right panel: AI chat sidebar (Cursor-like)."""
    
    def __init__(self):
        super().__init__()
        self.setObjectName("chatSidebarPanel")
        
        # Initialize ChatCore
        self.chat_core = ChatCore(
            system_prompt="You are a helpful assistant."
        )
        
        self._current_worker: ChatWorker = None
        self._streaming_card: StreamingMessageCard = None
        
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QLabel("AI Assistant")
        header.setObjectName("panelHeader")
        header.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setFixedHeight(32)
        layout.addWidget(header)
        
        # Chat history (scrollable)
        self.chat_history = ChatHistoryWidget()
        layout.addWidget(self.chat_history, 1)  # stretch factor 1
        
        # Chat input area
        self.chat_input = ChatInputWidget()
        layout.addWidget(self.chat_input)
        
        # Control bar (model selector + send button)
        self.control_bar = ChatControlBar()
        layout.addWidget(self.control_bar)
        
        # Connect signals
        self.control_bar.sendClicked.connect(self._on_send)
        self.control_bar.stopClicked.connect(self._on_stop)
        self.control_bar.modelChanged.connect(self._on_model_changed)
        
        # Add welcome message
        self._add_welcome_message()
        
    def _add_welcome_message(self):
        """Add initial welcome message."""
        self.chat_history.add_message(
            "assistant",
            "Hello! I'm your AI assistant for sentence building. "
            "I can help you merge word-timestamp ASR results into proper sentences.\n\n"
            "To get started:\n"
            "1. Select a model from the dropdown below\n"
            "2. Ask me anything!\n"
            "3. I support OpenAI, Claude, and Gemini models"
        )
    
    def _on_model_changed(self, model: str, provider: str):
        """Handle model selection change."""
        success = self.chat_core.set_model(model, provider)
        if success:
            print(f"[ChatSidebar] Model changed to: {model} @ {provider}")
        else:
            print(f"[ChatSidebar] Failed to set model: {model} @ {provider}")
        
    def _on_send(self):
        """Handle send button click."""
        text = self.chat_input.get_text()
        if not text.strip():
            return
        
        # Check if model is selected
        model, provider = self.control_bar.get_current_selection()
        if not model or not provider:
            self.chat_history.add_message(
                "assistant",
                "⚠️ Please select a model first using the dropdown below."
            )
            return
        
        # Ensure model is set in ChatCore
        if self.chat_core.get_current_model() != model:
            self.chat_core.set_model(model, provider)
        
        # Add user message to UI
        self.chat_history.add_message("user", text)
        self.chat_input.clear()
        
        # Create streaming message card
        self._streaming_card = self.chat_history.add_streaming_message()
        
        # Start worker thread
        self.control_bar.set_generating(True)
        self._current_worker = ChatWorker(self.chat_core, text)
        self._current_worker.chunk_received.connect(self._on_chunk_received)
        self._current_worker.response_complete.connect(self._on_response_complete)
        self._current_worker.error_occurred.connect(self._on_error)
        self._current_worker.start()
            
    def _on_chunk_received(self, chunk: str):
        """Handle incoming stream chunk."""
        if self._streaming_card:
            self._streaming_card.append_content(chunk)
            # Scroll to bottom
            self.chat_history.scroll_to_bottom()
    
    def _on_response_complete(self, response: str):
        """Handle response completion."""
        self.control_bar.set_generating(False)
        self._streaming_card = None
        self._current_worker = None
    
    def _on_error(self, error_msg: str):
        """Handle error during chat."""
        self.control_bar.set_generating(False)
        
        # Update streaming card to show error
        if self._streaming_card:
            self._streaming_card.set_error(f"Error: {error_msg}")
        else:
            self.chat_history.add_message(
                "assistant",
                f"❌ Error: {error_msg}"
            )
        
        self._streaming_card = None
        self._current_worker = None
            
    def _on_stop(self):
        """Handle stop button click."""
        if self._current_worker:
            self._current_worker.request_stop()
            self._current_worker.wait(1000)  # Wait up to 1 second
            self.control_bar.set_generating(False)
            
            if self._streaming_card:
                self._streaming_card.finalize("(Generation stopped)")


class ChatHistoryWidget(QScrollArea):
    """Scrollable chat history container."""
    
    def __init__(self):
        super().__init__()
        self.setObjectName("chatHistory")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Container widget
        self.container = QWidget()
        self.container.setObjectName("chatHistoryContainer")
        self.layout = QVBoxLayout(self.container)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(12)
        self.layout.addStretch()  # Push messages to top
        
        self.setWidget(self.container)
        
    def add_message(self, role: str, content: str):
        """Add a message card to the history.
        
        Args:
            role: 'user' or 'assistant'
            content: Message text
        """
        card = ChatMessageCard(role, content)
        # Insert before the stretch
        self.layout.insertWidget(self.layout.count() - 1, card)
        self.scroll_to_bottom()
        return card
    
    def add_streaming_message(self) -> 'StreamingMessageCard':
        """Add a streaming message card that can be updated."""
        card = StreamingMessageCard()
        self.layout.insertWidget(self.layout.count() - 1, card)
        self.scroll_to_bottom()
        return card
    
    def scroll_to_bottom(self):
        """Scroll to bottom of chat history."""
        # Use timer to ensure layout is updated
        QTimer.singleShot(10, lambda: self.verticalScrollBar().setValue(
            self.verticalScrollBar().maximum()
        ))
        
    def clear_history(self):
        """Clear all messages."""
        while self.layout.count() > 1:  # Keep the stretch
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


class ChatMessageCard(QFrame):
    """Individual chat message card."""
    
    def __init__(self, role: str, content: str):
        super().__init__()
        self.role = role
        self.setObjectName(f"chatMessage_{role}")
        self.init_ui(content)
        
    def init_ui(self, content: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        
        # Role label
        role_label = QLabel("You" if self.role == "user" else "Assistant")
        role_label.setObjectName("messageRole")
        role_label.setFont(QFont("Arial", 9, QFont.Bold))
        layout.addWidget(role_label)
        
        # Content label
        self.content_label = QLabel(content)
        self.content_label.setObjectName("messageContent")
        self.content_label.setWordWrap(True)
        self.content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.content_label)


class StreamingMessageCard(QFrame):
    """Message card that supports streaming updates."""
    
    def __init__(self):
        super().__init__()
        self.setObjectName("chatMessage_assistant")
        self._content = ""
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        
        # Role label
        role_label = QLabel("Assistant")
        role_label.setObjectName("messageRole")
        role_label.setFont(QFont("Arial", 9, QFont.Bold))
        layout.addWidget(role_label)
        
        # Content label
        self.content_label = QLabel("▍")  # Cursor indicator
        self.content_label.setObjectName("messageContent")
        self.content_label.setWordWrap(True)
        self.content_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.content_label)
    
    def append_content(self, chunk: str):
        """Append content chunk to the message."""
        self._content += chunk
        self.content_label.setText(self._content + "▍")
    
    def finalize(self, suffix: str = ""):
        """Finalize the message (remove cursor)."""
        if suffix:
            self._content += " " + suffix
        self.content_label.setText(self._content)
    
    def set_error(self, error_msg: str):
        """Set error state."""
        self._content = error_msg
        self.content_label.setText(self._content)
        self.content_label.setStyleSheet("color: #ff6b6b;")


class ChatInputWidget(QFrame):
    """Chat input text area."""
    
    def __init__(self):
        super().__init__()
        self.setObjectName("chatInputWidget")
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)
        
        self.text_edit = QPlainTextEdit()
        self.text_edit.setObjectName("chatInput")
        self.text_edit.setPlaceholderText("Type your message here...")
        self.text_edit.setMinimumHeight(60)
        self.text_edit.setMaximumHeight(120)
        layout.addWidget(self.text_edit)
        
    def get_text(self) -> str:
        """Get the current input text."""
        return self.text_edit.toPlainText()
        
    def clear(self):
        """Clear the input."""
        self.text_edit.clear()


class ChatControlBar(QFrame):
    """Control bar with model selector and send/stop button."""
    
    sendClicked = pyqtSignal()
    stopClicked = pyqtSignal()
    modelChanged = pyqtSignal(str, str)  # model, provider
    
    def __init__(self):
        super().__init__()
        self.setObjectName("chatControlBar")
        self.is_generating = False
        self.init_ui()
        
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Text chat model selector
        self.model_selector = ModelSelectorWidget(
            applicable_task="text-chat",
            max_popup_height=400
        )
        self.model_selector.selection_confirmed.connect(self._on_model_selected)
        layout.addWidget(self.model_selector)
        
        layout.addStretch()
        
        # Send/Stop button
        self.action_button = QPushButton("Send")
        self.action_button.setObjectName("sendButton")
        self.action_button.setMinimumWidth(80)
        self.action_button.clicked.connect(self._on_action_click)
        layout.addWidget(self.action_button)
    
    def _on_model_selected(self, model: str, provider: str):
        """Handle model selection."""
        print(f"[ChatControlBar] Text model selected: {model} @ {provider}")
        self.modelChanged.emit(model, provider)
    
    def get_current_selection(self) -> tuple:
        """Get current model selection."""
        return self.model_selector.get_current_selection()
        
    def _on_action_click(self):
        """Handle action button click."""
        if self.is_generating:
            self.stopClicked.emit()
            self.set_generating(False)
        else:
            self.sendClicked.emit()
            
    def set_generating(self, generating: bool):
        """Update button state based on generation status."""
        self.is_generating = generating
        if generating:
            self.action_button.setText("Stop")
            self.action_button.setObjectName("stopButton")
        else:
            self.action_button.setText("Send")
            self.action_button.setObjectName("sendButton")
        # Force style refresh
        self.action_button.style().unpolish(self.action_button)
        self.action_button.style().polish(self.action_button)
