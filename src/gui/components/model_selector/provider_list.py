"""
Provider List Widget - Right column showing available providers for selected model.
"""

from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QScrollArea, QWidget, QHBoxLayout, 
    QPushButton, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from typing import List, Optional

from .styles import ModelSelectorColors as Colors, COMMON_BASE_STYLE


class ProviderItem(QFrame):
    """A single provider item in the provider list."""
    
    clicked = pyqtSignal(str)  # provider_name
    star_toggled = pyqtSignal(str, bool)  # provider_name, new_status
    
    def __init__(self, provider_name: str, is_starred: bool = False, parent=None):
        super().__init__(parent)
        self.provider_name = provider_name
        self._is_starred = is_starred
        self._is_selected = False
        self._is_hovered = False
        
        self.setObjectName("providerItem")
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.init_ui()
        self._update_style()
    
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        
        # Provider name
        self.name_label = QLabel(self.provider_name)
        self.name_label.setObjectName("providerName")
        font = QFont()
        font.setPointSize(9)
        self.name_label.setFont(font)
        layout.addWidget(self.name_label, 1)
        
        # Star button
        self.star_button = QPushButton()
        self.star_button.setObjectName("providerStarButton")
        self.star_button.setFixedSize(22, 22)
        self.star_button.setCursor(Qt.PointingHandCursor)
        self.star_button.clicked.connect(self._on_star_clicked)
        layout.addWidget(self.star_button)
        
        self._update_star_display()
        
        self.setMinimumHeight(38)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    
    def _update_star_display(self):
        """Update star button appearance based on state."""
        if self._is_starred:
            self.star_button.setText("★")
            self.star_button.setStyleSheet("""
                QPushButton#providerStarButton {
                    background: transparent;
                    border: none;
                    font-size: 14px;
                    color: #f5a623;
                }
                QPushButton#providerStarButton:hover {
                    color: #ffc107;
                }
            """)
            self.star_button.setVisible(True)
        elif self._is_hovered:
            self.star_button.setText("☆")
            self.star_button.setStyleSheet("""
                QPushButton#providerStarButton {
                    background: transparent;
                    border: none;
                    font-size: 14px;
                    color: #999999;
                }
                QPushButton#providerStarButton:hover {
                    color: #666666;
                }
            """)
            self.star_button.setVisible(True)
        else:
            self.star_button.setVisible(False)
    
    def _update_style(self):
        """Update appearance based on selection state."""
        # 1. Base style
        base_style = COMMON_BASE_STYLE + f"""
            QFrame#providerItem {{
                background-color: {Colors.NORMAL_BG};
                border: 1px solid transparent;
                border-radius: 4px;
            }}
        """

        # 2. State specific style
        if self._is_selected:
            status_style = f"""
                QFrame#providerItem {{
                    background-color: {Colors.SELECTED_BG};
                    border: 1px solid {Colors.SELECTED_BORDER};
                }}
                QLabel#providerName {{
                    color: {Colors.SELECTED_TEXT};
                }}
            """
        else:
            status_style = f"""
                QFrame#providerItem:hover {{
                    background-color: {Colors.HOVER_BG};
                    border-color: {Colors.HOVER_BORDER};
                }}
                QLabel#providerName {{
                    color: {Colors.TEXT_PRIMARY};
                }}
            """
        
        # 3. Combine
        self.setStyleSheet(base_style + status_style)
    
    def _on_star_clicked(self):
        """Handle star button click."""
        self._is_starred = not self._is_starred
        self._update_star_display()
        self.star_toggled.emit(self.provider_name, self._is_starred)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Check if click was not on star button
            star_rect = self.star_button.geometry()
            if not star_rect.contains(event.pos()):
                self.clicked.emit(self.provider_name)
        super().mousePressEvent(event)
    
    def enterEvent(self, event):
        self._is_hovered = True
        self._update_star_display()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self._is_hovered = False
        self._update_star_display()
        super().leaveEvent(event)
    
    def set_selected(self, selected: bool):
        """Set selection state."""
        if self._is_selected != selected:
            self._is_selected = selected
            self._update_style()
    
    def set_starred(self, starred: bool):
        """Set starred state without emitting signal."""
        if self._is_starred != starred:
            self._is_starred = starred
            self._update_star_display()
    
    def is_selected(self) -> bool:
        return self._is_selected
    
    def is_starred(self) -> bool:
        return self._is_starred


class ProviderList(QFrame):
    """Scrollable list of providers for the selected model."""
    
    provider_clicked = pyqtSignal(str)  # provider_name
    provider_star_toggled = pyqtSignal(str, bool)  # provider_name, new_status
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("providerList")
        self._provider_items: dict[str, ProviderItem] = {}
        self._current_selection: str | None = None
        self.init_ui()
    
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header
        header = QLabel("Providers:")
        header.setObjectName("providerListHeader")
        header.setStyleSheet("""
            QLabel#providerListHeader {
                color: #666666;
                font-size: 10px;
                padding: 6px 8px;
                background-color: #f3f3f3;
                border-bottom: 1px solid #e0e0e0;
            }
        """)
        main_layout.addWidget(header)
        
        # Scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("providerScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea#providerScrollArea {
                background-color: #f7f7f7;
                border: none;
            }
            QScrollBar:vertical {
                width: 8px;
                background: #f7f7f7;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a0a0a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)
        
        # Container for provider items
        self.container = QWidget()
        self.container.setObjectName("providerContainer")
        self.container.setStyleSheet("background-color: #f7f7f7;")
        self.items_layout = QVBoxLayout(self.container)
        self.items_layout.setContentsMargins(4, 4, 4, 4)
        self.items_layout.setSpacing(4)
        self.items_layout.addStretch()
        
        # Placeholder
        self.placeholder = QLabel("Select a model")
        self.placeholder.setObjectName("providerPlaceholder")
        self.placeholder.setAlignment(Qt.AlignCenter)
        self.placeholder.setStyleSheet("""
            QLabel#providerPlaceholder {
                color: #999999;
                font-size: 10px;
                padding: 20px;
            }
        """)
        self.items_layout.insertWidget(0, self.placeholder)
        
        self.scroll_area.setWidget(self.container)
        main_layout.addWidget(self.scroll_area)
        
        self.setMinimumWidth(100)
        self.setStyleSheet("""
            QFrame#providerList {
                background-color: #f7f7f7;
                border-left: 1px solid #e0e0e0;
            }
        """)
    
    def set_providers(self, providers: List[str], starred_provider: Optional[str] = None):
        """Set the list of providers to display."""
        # Clear existing items
        self._provider_items.clear()
        self._current_selection = None
        
        while self.items_layout.count() > 1:  # Keep stretch
            item = self.items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not providers:
            # Show placeholder
            self.placeholder = QLabel("No providers")
            self.placeholder.setObjectName("providerPlaceholder")
            self.placeholder.setAlignment(Qt.AlignCenter)
            self.placeholder.setStyleSheet("""
                QLabel#providerPlaceholder {
                    color: #999999;
                    font-size: 10px;
                    padding: 20px;
                }
            """)
            self.items_layout.insertWidget(0, self.placeholder)
            return
        
        # Add provider items
        for provider_name in providers:
            is_starred = provider_name == starred_provider
            item = ProviderItem(provider_name, is_starred=is_starred)
            item.clicked.connect(self._on_item_clicked)
            item.star_toggled.connect(self._on_star_toggled)
            self.items_layout.insertWidget(self.items_layout.count() - 1, item)
            self._provider_items[provider_name] = item
            
            # Auto-select starred provider
            if is_starred:
                self._current_selection = provider_name
                item.set_selected(True)
        
        # If no starred, select first
        if self._current_selection is None and providers:
            first_provider = providers[0]
            self._current_selection = first_provider
            self._provider_items[first_provider].set_selected(True)
    
    def _on_item_clicked(self, provider_name: str):
        """Handle provider item click."""
        self.select_provider(provider_name)
        self.provider_clicked.emit(provider_name)
    
    def _on_star_toggled(self, provider_name: str, new_status: bool):
        """Handle star toggle - ensure only one is starred."""
        if new_status:
            # Unstar all others
            for name, item in self._provider_items.items():
                if name != provider_name and item.is_starred():
                    item.set_starred(False)
        
        self.provider_star_toggled.emit(provider_name, new_status)
    
    def select_provider(self, provider_name: str):
        """Select a provider."""
        if self._current_selection == provider_name:
            return
        
        # Deselect previous
        if self._current_selection and self._current_selection in self._provider_items:
            self._provider_items[self._current_selection].set_selected(False)
        
        # Select new
        self._current_selection = provider_name
        if provider_name in self._provider_items:
            self._provider_items[provider_name].set_selected(True)
    
    def get_selected_provider(self) -> Optional[str]:
        return self._current_selection
    
    def get_starred_provider(self) -> Optional[str]:
        """Get currently starred provider name."""
        for name, item in self._provider_items.items():
            if item.is_starred():
                return name
        return None
