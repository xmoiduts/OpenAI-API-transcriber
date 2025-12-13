"""
Family List Widget - Left column showing model families for navigation.
"""

from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QScrollArea, QWidget, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont
from typing import List

from .styles import ModelSelectorColors as Colors, COMMON_BASE_STYLE


class FamilyItem(QFrame):
    """A single family item in the family list."""
    
    clicked = pyqtSignal(str)  # family_name
    
    def __init__(self, family_name: str, is_starred_section: bool = False, parent=None):
        super().__init__(parent)
        self.family_name = family_name
        self.is_starred_section = is_starred_section
        self._is_highlighted = False
        
        self.setObjectName("familyItem")
        self.setCursor(Qt.PointingHandCursor)
        self.init_ui()
        self._update_style()
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        
        # Family name label
        display_text = "★ Starred" if self.is_starred_section else self.family_name
        self.label = QLabel(display_text)
        self.label.setObjectName("familyLabel")
        
        font = QFont()
        font.setPointSize(8)
        if self.is_starred_section:
            font.setBold(True)
        self.label.setFont(font)
        
        layout.addWidget(self.label)
        
        self.setMinimumHeight(32)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    
    def _update_style(self):
        """Update appearance based on highlight state."""
        # 1. Base style
        base_style = COMMON_BASE_STYLE + f"""
            QFrame#familyItem {{
                background-color: {Colors.NORMAL_BG};
                border-radius: 4px;
            }}
        """

        # 2. State specific style
        if self._is_highlighted:
            status_style = f"""
                QFrame#familyItem {{
                    background-color: {Colors.SELECTED_BG};
                }}
                QLabel#familyLabel {{
                    color: {Colors.SELECTED_TEXT};
                }}
            """
        else:
            if self.is_starred_section:
                status_style = f"""
                    QFrame#familyItem:hover {{
                        background-color: {Colors.HOVER_BG};
                    }}
                    QLabel#familyLabel {{
                        color: {Colors.TEXT_STARRED};
                    }}
                """
            else:
                status_style = f"""
                    QFrame#familyItem:hover {{
                        background-color: {Colors.HOVER_BG};
                    }}
                    QLabel#familyLabel {{
                        color: {Colors.TEXT_PRIMARY};
                    }}
                """
        
        # 3. Combine
        self.setStyleSheet(base_style + status_style)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.family_name)
        super().mousePressEvent(event)
    
    def set_highlighted(self, highlighted: bool):
        """Set highlight state."""
        if self._is_highlighted != highlighted:
            self._is_highlighted = highlighted
            self._update_style()
    
    def is_highlighted(self) -> bool:
        return self._is_highlighted


class FamilyList(QFrame):
    """Scrollable list of model families."""
    
    family_clicked = pyqtSignal(str)  # family_name
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("familyList")
        self._family_items: dict[str, FamilyItem] = {}
        self._current_highlight: str | None = None
        self.init_ui()
    
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header
        header = QLabel("Model Family:")
        header.setObjectName("familyListHeader")
        header.setStyleSheet("""
            QLabel#familyListHeader {
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
        self.scroll_area.setObjectName("familyScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setStyleSheet("""
            QScrollArea#familyScrollArea {
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
        
        # Container for family items
        self.container = QWidget()
        self.container.setObjectName("familyContainer")
        self.container.setStyleSheet("background-color: #f7f7f7;")
        self.items_layout = QVBoxLayout(self.container)
        self.items_layout.setContentsMargins(4, 4, 4, 4)
        self.items_layout.setSpacing(2)
        self.items_layout.addStretch()
        
        self.scroll_area.setWidget(self.container)
        main_layout.addWidget(self.scroll_area)
        
        self.setFixedWidth(100)
        self.setStyleSheet("""
            QFrame#familyList {
                background-color: #f7f7f7;
                border-right: 1px solid #e0e0e0;
            }
        """)
    
    def set_families(self, families: List[str], has_starred: bool = True):
        """Set the list of families to display."""
        # Clear existing items
        self._family_items.clear()
        while self.items_layout.count() > 1:  # Keep stretch
            item = self.items_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add starred section if has starred models
        if has_starred:
            starred_item = FamilyItem("★ Starred", is_starred_section=True)
            starred_item.clicked.connect(self._on_item_clicked)
            self.items_layout.insertWidget(self.items_layout.count() - 1, starred_item)
            self._family_items["★ Starred"] = starred_item
        
        # Add family items
        for family in families:
            item = FamilyItem(family)
            item.clicked.connect(self._on_item_clicked)
            self.items_layout.insertWidget(self.items_layout.count() - 1, item)
            self._family_items[family] = item
    
    def _on_item_clicked(self, family_name: str):
        """Handle family item click."""
        self.family_clicked.emit(family_name)
    
    def set_highlighted_family(self, family_name: str | None):
        """Set which family is highlighted."""
        if self._current_highlight == family_name:
            return
        
        # Unhighlight previous
        if self._current_highlight and self._current_highlight in self._family_items:
            self._family_items[self._current_highlight].set_highlighted(False)
        
        # Highlight new
        self._current_highlight = family_name
        if family_name and family_name in self._family_items:
            self._family_items[family_name].set_highlighted(True)
    
    def get_highlighted_family(self) -> str | None:
        return self._current_highlight

