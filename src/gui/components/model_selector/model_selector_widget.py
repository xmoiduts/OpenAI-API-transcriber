"""
Model Selector Widget - Main widget with trigger button and popup management.

Usage:
    selector = ModelSelectorWidget(applicable_task="audio-transcription")
    selector.selection_confirmed.connect(on_model_selected)
"""

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QSizePolicy, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QPoint
from PyQt5.QtGui import QFont
from typing import Optional

from .model_selector_popup import ModelSelectorPopup


class ModelSelectorWidget(QWidget):
    """A widget for selecting AI models and providers.
    
    Displays a button that opens a three-column popup for model selection.
    
    Args:
        applicable_task: Task type filter (e.g., "audio-transcription", "text-chat")
        max_popup_height: Maximum height of the popup panel in pixels
        parent: Parent widget
    
    Signals:
        selection_confirmed: Emitted when selection is confirmed (model_key, provider_name)
        selection_changed: Emitted when selection changes but not confirmed
    """
    
    selection_confirmed = pyqtSignal(str, str)  # model_key, provider_name
    selection_changed = pyqtSignal(str, str)    # model_key, provider_name
    
    def __init__(
        self,
        applicable_task: str,
        max_popup_height: int = 400,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        
        self._applicable_task = applicable_task
        self._max_popup_height = max_popup_height
        
        self._current_model: Optional[str] = None
        self._current_provider: Optional[str] = None
        self._current_display_name: str = "Select Model"
        
        self._popup: Optional[ModelSelectorPopup] = None
        
        self.setObjectName("modelSelectorWidget")
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Trigger button
        self.trigger_button = QPushButton()
        self.trigger_button.setObjectName("modelSelectorButton")
        self.trigger_button.setCursor(Qt.PointingHandCursor)
        self.trigger_button.clicked.connect(self._toggle_popup)
        self._update_button_text()
        
        self.trigger_button.setStyleSheet("""
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
            QPushButton#modelSelectorButton:pressed {
                background-color: #e8e8e8;
            }
        """)
        
        layout.addWidget(self.trigger_button)
        
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    
    def _update_button_text(self):
        """Update button text with current selection."""
        if self._current_model and self._current_provider:
            text = f"{self._current_display_name} ▼"
        else:
            text = "Select Model ▼"
        self.trigger_button.setText(text)
    
    def _toggle_popup(self):
        """Toggle popup visibility."""
        if self._popup and self._popup.isVisible():
            self._close_popup()
        else:
            self._open_popup()
    
    def _open_popup(self):
        """Open the model selector popup."""
        # Create popup if needed
        if self._popup is None:
            self._popup = ModelSelectorPopup(
                applicable_task=self._applicable_task,
                max_height=self._max_popup_height,
                parent=None  # Top-level window for proper popup behavior
            )
            self._popup.selection_changed.connect(self._on_selection_changed)
            self._popup.close_requested.connect(self._close_popup)
        
        # Restore previous selection if any
        if self._current_model and self._current_provider:
            self._popup.set_selection(self._current_model, self._current_provider)
        
        # Calculate position - prefer below button, but above if no space
        button_global = self.trigger_button.mapToGlobal(QPoint(0, 0))
        button_height = self.trigger_button.height()
        
        screen = QApplication.screenAt(button_global)
        if screen:
            screen_rect = screen.availableGeometry()
        else:
            screen_rect = QApplication.primaryScreen().availableGeometry()
        
        popup_height = min(self._max_popup_height, self._popup.sizeHint().height())
        popup_width = self._popup.sizeHint().width()
        
        # Check space below
        space_below = screen_rect.bottom() - (button_global.y() + button_height)
        space_above = button_global.y() - screen_rect.top()
        
        if space_below >= popup_height or space_below >= space_above:
            # Show below
            popup_y = button_global.y() + button_height + 4
        else:
            # Show above
            popup_y = button_global.y() - popup_height - 4
        
        # Align left edge of Model Cards (2nd column) with button
        # Popup structure: [Family List | Model Cards | Providers]
        # So we shift left by width of Family List
        family_width = 100  # Default width
        if hasattr(self._popup, 'family_list'):
            family_width = self._popup.family_list.width()
            
        popup_x = button_global.x() - family_width
        
        # Ensure on screen
        if popup_x < screen_rect.left():
            popup_x = screen_rect.left() + 5
            
        if popup_x + popup_width > screen_rect.right():
            popup_x = screen_rect.right() - popup_width - 5
        
        self._popup.move(popup_x, popup_y)
        self._popup.show()
        self._popup.setFocus()
    
    def _close_popup(self):
        """Close the popup and emit confirmation."""
        if self._popup:
            # Get final selection
            model, provider = self._popup.get_current_selection()
            
            self._popup.hide()
            
            if model and provider:
                self._current_model = model
                self._current_provider = provider
                
                # Get display name from popup's model data
                if hasattr(self._popup, '_models') and model in self._popup._models:
                    self._current_display_name = self._popup._models[model].get(
                        'display-name', model
                    )
                else:
                    self._current_display_name = model
                
                self._update_button_text()
                self.selection_confirmed.emit(model, provider)
    
    def _on_selection_changed(self, model: str, provider: str):
        """Handle selection change in popup."""
        self.selection_changed.emit(model, provider)
    
    # Public API
    
    def get_current_selection(self) -> tuple:
        """Get current selection as (model_key, provider_name).
        
        Returns:
            Tuple of (model_key, provider_name). Values may be None if nothing selected.
        """
        return (self._current_model, self._current_provider)
    
    def set_selection(self, model: str, provider: str) -> bool:
        """Set current selection programmatically.
        
        Args:
            model: Model key to select
            provider: Provider name to select
            
        Returns:
            True if selection was successful, False otherwise.
        """
        # Create popup temporarily to validate and get display name
        if self._popup is None:
            self._popup = ModelSelectorPopup(
                applicable_task=self._applicable_task,
                max_height=self._max_popup_height,
                parent=None
            )
            self._popup.selection_changed.connect(self._on_selection_changed)
            self._popup.close_requested.connect(self._close_popup)
        
        if self._popup.set_selection(model, provider):
            self._current_model = model
            self._current_provider = provider
            
            if model in self._popup._models:
                self._current_display_name = self._popup._models[model].get(
                    'display-name', model
                )
            else:
                self._current_display_name = model
            
            self._update_button_text()
            return True
        
        return False
    
    def refresh_models(self):
        """Reload models from configuration file."""
        if self._popup:
            self._popup.deleteLater()
            self._popup = None
        
        # Will be recreated on next open
    
    @property
    def applicable_task(self) -> str:
        """Get the applicable task filter (read-only)."""
        return self._applicable_task

