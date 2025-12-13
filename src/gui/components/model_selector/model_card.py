"""
Model Card Widget - Individual model card in the model list.
Displays: display-name (large), api-name (small, gray), star button (right)
"""

from PyQt5.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from .styles import ModelSelectorColors as Colors, COMMON_BASE_STYLE


class ModelCard(QFrame):
    """A card widget representing a single model."""
    
    # Signals
    clicked = pyqtSignal(str)  # model_key
    star_toggled = pyqtSignal(str, bool)  # model_key, new_starred_status
    
    def __init__(
        self,
        model_key: str,
        display_name: str,
        model_family: str,
        is_starred: bool = False,
        parent=None
    ):
        super().__init__(parent)
        self.model_key = model_key
        self.display_name = display_name
        self.model_family = model_family
        self._is_starred = is_starred
        self._is_selected = False
        
        self.setObjectName("modelCard")
        self.setCursor(Qt.PointingHandCursor)
        self.init_ui()
        self._update_style()
    
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        
        # Left side: text content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        
        # Display name (large)
        self.name_label = QLabel(self.display_name)
        self.name_label.setObjectName("modelCardName")
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        self.name_label.setFont(font)
        text_layout.addWidget(self.name_label)
        
        # API name (small, gray)
        self.api_label = QLabel(self.model_key)
        self.api_label.setObjectName("modelCardApiName")
        api_font = QFont()
        api_font.setPointSize(9)
        self.api_label.setFont(api_font)
        text_layout.addWidget(self.api_label)
        
        layout.addLayout(text_layout, 1)
        
        # Right side: star button
        self.star_button = QPushButton()
        self.star_button.setObjectName("starButton")
        self.star_button.setFixedSize(28, 28)
        self.star_button.setCursor(Qt.PointingHandCursor)
        self.star_button.clicked.connect(self._on_star_clicked)
        self._update_star_display()
        layout.addWidget(self.star_button)
        
        self.setMinimumHeight(54)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    
    def _update_star_display(self):
        """Update star button appearance."""
        if self._is_starred:
            self.star_button.setText("★")
            self.star_button.setStyleSheet("""
                QPushButton#starButton {
                    background: transparent;
                    border: none;
                    font-size: 18px;
                    color: #f5a623;
                }
                QPushButton#starButton:hover {
                    color: #ffc107;
                }
            """)
        else:
            self.star_button.setText("☆")
            self.star_button.setStyleSheet("""
                QPushButton#starButton {
                    background: transparent;
                    border: none;
                    font-size: 18px;
                    color: #999999;
                }
                QPushButton#starButton:hover {
                    color: #666666;
                }
            """)
    
    def _update_style(self):
        """Update card appearance based on selection state."""
        # 1. Base style (transparency)
        base_style = COMMON_BASE_STYLE + f"""
            QFrame#modelCard {{
                background-color: {Colors.NORMAL_BG};
                border-radius: 6px;
            }}
        """

        # 2. State specific style
        if self._is_selected:
            status_style = f"""
                QFrame#modelCard {{
                    background-color: {Colors.SELECTED_BG};
                    border: 1px solid {Colors.SELECTED_BORDER};
                }}
                QLabel#modelCardName {{
                    color: {Colors.SELECTED_TEXT};
                }}
                QLabel#modelCardApiName {{
                    color: {Colors.SELECTED_SUBTEXT};
                }}
            """
        else:
            status_style = f"""
                QFrame#modelCard {{
                    border: 1px solid {Colors.NORMAL_BORDER};
                }}
                QFrame#modelCard:hover {{
                    background-color: {Colors.HOVER_BG};
                    border-color: {Colors.HOVER_BORDER};
                }}
                QLabel#modelCardName {{
                    color: {Colors.TEXT_PRIMARY};
                }}
                QLabel#modelCardApiName {{
                    color: {Colors.TEXT_SECONDARY};
                }}
            """
            
        # 3. Combine
        self.setStyleSheet(base_style + status_style)
    
    def _on_star_clicked(self):
        """Handle star button click."""
        self._is_starred = not self._is_starred
        self._update_star_display()
        self.star_toggled.emit(self.model_key, self._is_starred)
    
    def mousePressEvent(self, event):
        """Handle card click."""
        if event.button() == Qt.LeftButton:
            # Check if click was not on star button
            star_rect = self.star_button.geometry()
            if not star_rect.contains(event.pos()):
                self.clicked.emit(self.model_key)
        super().mousePressEvent(event)
    
    def set_selected(self, selected: bool):
        """Set selection state."""
        if self._is_selected != selected:
            self._is_selected = selected
            self._update_style()
    
    def set_starred(self, starred: bool):
        """Set starred state (without emitting signal)."""
        if self._is_starred != starred:
            self._is_starred = starred
            self._update_star_display()
    
    def is_selected(self) -> bool:
        return self._is_selected
    
    def is_starred(self) -> bool:
        return self._is_starred

