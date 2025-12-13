"""
Model Selector Popup - Three-column popup panel for model selection.
Layout: [Model Family | Model Cards | Providers]
"""

from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, 
    QWidget, QPushButton, QSizePolicy, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, pyqtProperty, QEasingCurve, QPoint, QSize
from PyQt5.QtGui import QFont, QColor
from typing import List, Dict, Optional, Any
import yaml
from collections import defaultdict

from .family_list import FamilyList
from .model_card import ModelCard
from .provider_list import ProviderList
from .starred_storage import get_starred_storage


class SectionHeader(QLabel):
    """Header for model family sections with flash animation support."""
    
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self._default_style = """
            color: #666666;
            font-size: 10px;
            font-weight: bold;
            padding: 4px 6px;
            margin-top: 8px;
            border-radius: 4px;
        """
        # Initial style with transparent background
        self.setStyleSheet(f"QLabel {{ {self._default_style} background-color: transparent; }}")
        self._bg_color = QColor(0, 0, 0, 0)

    @pyqtProperty(QColor)
    def backgroundColor(self):
        return self._bg_color

    @backgroundColor.setter
    def backgroundColor(self, color):
        self._bg_color = color
        r, g, b, a = color.red(), color.green(), color.blue(), color.alpha()
        # Re-apply style with new background
        self.setStyleSheet(f"""
            QLabel {{
                {self._default_style}
                background-color: rgba({r}, {g}, {b}, {a});
            }}
        """)

    def flash(self):
        """Trigger a flash animation (highlight then fade out)."""
        # Create animation if not exists or reuse
        self.anim = QPropertyAnimation(self, b"backgroundColor")
        self.anim.setDuration(1500) # 1.5s fade out
        start_color = QColor(255, 248, 225, 255) # Light yellow/orange highlight
        end_color = QColor(255, 248, 225, 0) # Same color but transparent
        
        self.anim.setStartValue(start_color)
        self.anim.setEndValue(end_color)
        self.anim.setEasingCurve(QEasingCurve.OutQuad)
        self.anim.start()


class ModelSelectorPopup(QFrame):
    """Three-column popup for model selection."""
    
    # Signals
    selection_changed = pyqtSignal(str, str)  # model_key, provider_name
    close_requested = pyqtSignal()
    
    def __init__(
        self, 
        applicable_task: str,
        max_height: int = 400,
        parent=None
    ):
        super().__init__(parent)
        self.applicable_task = applicable_task
        self.max_height = max_height
        
        self._config: Dict = {}
        self._models: Dict[str, Dict] = {}  # Filtered models
        self._families: List[str] = []
        
        # Mapping model_key -> list of ModelCard instances (to handle both starred and family sections)
        self._all_model_cards: Dict[str, List[ModelCard]] = defaultdict(list)
        # Mapping model_key -> primary ModelCard (the one in the family section) for scroll detection
        self._primary_model_cards: Dict[str, ModelCard] = {}
        
        self._family_headers: Dict[str, SectionHeader] = {} # family/starred -> header widget
        self._family_first_model: Dict[str, str] = {}  # family -> first model_key
        self._model_to_family: Dict[str, str] = {}  # model_key -> family
        
        self._current_model: Optional[str] = None
        self._current_provider: Optional[str] = None
        
        self._storage = get_starred_storage()
        
        self.setObjectName("modelSelectorPopup")
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        
        # For resize handling
        self._resize_dragging = False
        self._drag_start_pos = QPoint()
        self._drag_start_size = QSize()
        self._resize_margin = 12  # pixels from edge to trigger resize cursor
        
        self.init_ui()
        self._load_config()
        self._populate_models()
    
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Outer frame for border
        self.outer_frame = QFrame()
        self.outer_frame.setObjectName("popupOuterFrame")
        self.outer_frame.setStyleSheet("""
            QFrame#popupOuterFrame {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 8px;
            }
        """)
        
        # Resize grip indicator (bottom-right corner)
        self.resize_grip = QLabel("⋱", self)
        self.resize_grip.setObjectName("resizeGrip")
        self.resize_grip.setFixedSize(16, 16)
        self.resize_grip.setAlignment(Qt.AlignCenter)
        self.resize_grip.setStyleSheet("""
            QLabel#resizeGrip {
                color: #999999;
                font-size: 12px;
                background: transparent;
            }
        """)
        self.resize_grip.setCursor(Qt.SizeFDiagCursor)
        self.resize_grip.setAttribute(Qt.WA_TransparentForMouseEvents)  # Let events pass through
        
        outer_layout = QVBoxLayout(self.outer_frame)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)
        
        # Three-column content area
        content_frame = QFrame()
        content_frame.setObjectName("contentFrame")
        content_layout = QHBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # Column 1: Family List
        self.family_list = FamilyList()
        self.family_list.family_clicked.connect(self._on_family_clicked)
        content_layout.addWidget(self.family_list)
        
        # Column 2: Model Cards (scrollable)
        self.model_column = QFrame()
        self.model_column.setObjectName("modelColumn")
        self.model_column.setStyleSheet("""
            QFrame#modelColumn {
                background-color: #fafafa;
            }
        """)
        model_column_layout = QVBoxLayout(self.model_column)
        model_column_layout.setContentsMargins(0, 0, 0, 0)
        model_column_layout.setSpacing(0)
        
        # Header bar (Moved inside model column)
        header_bar = QFrame()
        header_bar.setObjectName("popupHeaderBar")
        header_bar.setStyleSheet("""
            QFrame#popupHeaderBar {
                background-color: #f3f3f3;
                border-bottom: 1px solid #e0e0e0;
                /* Remove top radius as it's no longer top of window */
            }
        """)
        header_bar.setFixedHeight(36)
        
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(12, 0, 12, 0)
        
        # Task badge
        task_badge = QPushButton(self._format_task_name())
        task_badge.setFixedSize(80, 24)
        task_badge.setObjectName("taskBadge")
        task_badge.setStyleSheet("""
            QPushButton#taskBadge {
                background-color: #1976d2;
                color: #ffffff;
                padding: 3px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
        """)
        header_layout.addWidget(task_badge)
        
        # Model label
        model_label = QLabel("Model:")
        model_label.setStyleSheet("color: #666666; font-size: 11px;")
        header_layout.addWidget(model_label)
        
        header_layout.addStretch()
        
        # OK button
        self.ok_button = QPushButton("OK")
        self.ok_button.setObjectName("okButton")
        self.ok_button.setFixedSize(50, 24)
        self.ok_button.setCursor(Qt.PointingHandCursor)
        self.ok_button.clicked.connect(self._on_ok_clicked)
        self.ok_button.setStyleSheet("""
            QPushButton#okButton {
                background-color: #1976d2;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton#okButton:hover {
                background-color: #1e88e5;
            }
            QPushButton#okButton:pressed {
                background-color: #1565c0;
            }
        """)
        header_layout.addWidget(self.ok_button)
        
        model_column_layout.addWidget(header_bar)
        
        self.model_scroll = QScrollArea()
        self.model_scroll.setObjectName("modelScrollArea")
        self.model_scroll.setWidgetResizable(True)
        self.model_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.model_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.model_scroll.setStyleSheet("""
            QScrollArea#modelScrollArea {
                background-color: #fafafa;
                border: none;
            }
            QScrollBar:vertical {
                width: 8px;
                background: #fafafa;
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
        self.model_scroll.verticalScrollBar().valueChanged.connect(self._on_model_scroll)
        
        self.model_container = QWidget()
        self.model_container.setStyleSheet("background-color: #fafafa;")
        self.model_layout = QVBoxLayout(self.model_container)
        self.model_layout.setContentsMargins(8, 8, 8, 8)
        self.model_layout.setSpacing(6)
        self.model_layout.addStretch()
        
        self.model_scroll.setWidget(self.model_container)
        model_column_layout.addWidget(self.model_scroll)
        
        self.model_column.setMinimumWidth(250)
        content_layout.addWidget(self.model_column, 1)  # stretch
        
        # Column 3: Providers
        self.provider_list = ProviderList()
        self.provider_list.provider_clicked.connect(self._on_provider_clicked)
        self.provider_list.provider_star_toggled.connect(self._on_provider_star_toggled)
        content_layout.addWidget(self.provider_list)
        
        outer_layout.addWidget(content_frame, 1)
        
        main_layout.addWidget(self.outer_frame)
        
        # Enable mouse tracking for resize cursor changes
        self.setMouseTracking(True)
        
        # Set size constraints
        self.setMinimumSize(450, 250)
        self.resize(550, self.max_height)
    
    def _format_task_name(self) -> str:
        """Format task name for display."""
        mapping = {
            "text-chat": "Chat",
            "audio-transcription": "Audio"
        }
        if self.applicable_task in mapping:
            return mapping[self.applicable_task]
        return self.applicable_task.replace("-", " ").title()
    
    def _load_config(self):
        """Load configuration from config.yaml."""
        try:
            # Try multiple possible locations
            from pathlib import Path
            current = Path(__file__).resolve()
            
            config_path = None
            for parent in current.parents:
                if (parent / "config.yaml").exists():
                    config_path = parent / "config.yaml"
                    break
            
            if config_path:
                with open(config_path, 'r', encoding='utf-8') as f:
                    self._config = yaml.safe_load(f) or {}
            else:
                print("[ModelSelector] Warning: config.yaml not found")
                self._config = {}
                
        except Exception as e:
            print(f"[ModelSelector] Error loading config: {e}")
            self._config = {}
    
    def _populate_models(self):
        """Filter and populate models based on applicable_task."""
        models_config = self._config.get('api', {}).get('models', {})
        
        # Filter models by applicable task
        self._models = {}
        families_set = set()
        
        for model_key, model_data in models_config.items():
            applicable_tasks = model_data.get('applicable-tasks', [])
            if self.applicable_task in applicable_tasks:
                self._models[model_key] = model_data
                family = model_data.get('model-family', 'Other')
                families_set.add(family)
                self._model_to_family[model_key] = family
        
        # Sort families
        self._families = sorted(list(families_set))
        
        # Check if there are starred models
        starred_models = self._storage.get_starred_models()
        has_starred = any(m in self._models for m in starred_models)
        
        # Populate family list
        self.family_list.set_families(self._families, has_starred=has_starred)
        
        # Build model cards
        self._build_model_cards()
        
        # Select first model by default
        if self._primary_model_cards:
            first_model = next(iter(self._primary_model_cards.keys()))
            self._select_model(first_model)
    
    def _build_model_cards(self):
        """Build and arrange model cards."""
        # Clear existing cards
        self._all_model_cards.clear()
        self._primary_model_cards.clear()
        self._family_headers.clear()
        self._family_first_model.clear()
        
        while self.model_layout.count() > 1:  # Keep stretch
            item = self.model_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        starred_models = self._storage.get_starred_models()
        
        # First add starred section if any
        starred_in_task = [m for m in starred_models if m in self._models]
        if starred_in_task:
            # Add starred section header
            starred_header = SectionHeader("★ Starred")
            # Style is now handled by SectionHeader class
            starred_header.setStyleSheet(starred_header.styleSheet() + """
                QLabel { color: #f5a623; }
            """)
            self.model_layout.insertWidget(self.model_layout.count() - 1, starred_header)
            self._family_headers["★ Starred"] = starred_header
            
            # Add starred model cards
            for model_key in starred_in_task:
                model_data = self._models[model_key]
                card = self._create_model_card(model_key, model_data, is_starred=True)
                self.model_layout.insertWidget(self.model_layout.count() - 1, card)
                self._all_model_cards[model_key].append(card)
            
            self._family_first_model["★ Starred"] = starred_in_task[0] if starred_in_task else None
        
        # Add models by family
        for family in self._families:
            # Add family header
            family_header = SectionHeader(family)
            self.model_layout.insertWidget(self.model_layout.count() - 1, family_header)
            self._family_headers[family] = family_header
            
            # Add models in this family
            first_in_family = True
            family_models = [(k, v) for k, v in self._models.items() 
                            if v.get('model-family') == family]
            family_models.sort(key=lambda x: x[1].get('display-name', x[0]))
            
            for model_key, model_data in family_models:
                is_starred = model_key in starred_models
                card = self._create_model_card(model_key, model_data, is_starred=is_starred)
                self.model_layout.insertWidget(self.model_layout.count() - 1, card)
                self._all_model_cards[model_key].append(card)
                self._primary_model_cards[model_key] = card
                
                if first_in_family:
                    self._family_first_model[family] = model_key
                    first_in_family = False
    
    def _create_model_card(self, model_key: str, model_data: Dict, is_starred: bool) -> ModelCard:
        """Create a model card widget."""
        display_name = model_data.get('display-name', model_key)
        model_family = model_data.get('model-family', 'Other')
        
        card = ModelCard(
            model_key=model_key,
            display_name=display_name,
            model_family=model_family,
            is_starred=is_starred
        )
        card.clicked.connect(self._on_model_card_clicked)
        card.star_toggled.connect(self._on_model_star_toggled)
        
        return card
    
    def _select_model(self, model_key: str):
        """Select a model and update providers."""
        if model_key == self._current_model:
            return  # Don't re-select same model
        
        # Deselect previous in all locations
        if self._current_model and self._current_model in self._all_model_cards:
            for card in self._all_model_cards[self._current_model]:
                card.set_selected(False)
        
        self._current_model = model_key
        
        # Select new in all locations
        if model_key in self._all_model_cards:
            for card in self._all_model_cards[model_key]:
                card.set_selected(True)
        
        # Update family highlight
        family = self._model_to_family.get(model_key, "")
        self.family_list.set_highlighted_family(family)
        
        # Update providers
        self._update_providers()
        
        # Debug output
        self._debug_print_selection()
    
    def _update_providers(self):
        """Update provider list for current model."""
        if not self._current_model:
            self.provider_list.set_providers([])
            return
        
        model_data = self._models.get(self._current_model, {})
        providers_config = model_data.get('providers', {})
        
        # Handle edge case: providers_config might be None or non-dict
        if not isinstance(providers_config, dict):
            print(f"[ModelSelector] Warning: providers_config for model '{self._current_model}' is not a dict: {type(providers_config).__name__} = {providers_config}")
            providers_config = {}
        
        providers = list(providers_config.keys())
        
        # Get starred provider for this model
        starred_provider = self._storage.get_starred_provider(self._current_model)
        
        self.provider_list.set_providers(providers, starred_provider)
        
        # Set current provider
        self._current_provider = self.provider_list.get_selected_provider()
        
        # Emit change
        if self._current_model and self._current_provider:
            self.selection_changed.emit(self._current_model, self._current_provider)
    
    def _on_model_card_clicked(self, model_key: str):
        """Handle model card click."""
        self._select_model(model_key)
    
    def _on_model_star_toggled(self, model_key: str, new_status: bool):
        """Handle model star toggle."""
        self._storage.toggle_model_star(model_key)
        # Rebuild to update starred section
        QTimer.singleShot(0, self._rebuild_model_list)
    
    def _rebuild_model_list(self):
        """Rebuild the model list (after star change)."""
        current = self._current_model
        self._build_model_cards()
        if current:
            # Re-apply selection to new cards
            if current in self._all_model_cards:
                for card in self._all_model_cards[current]:
                    card.set_selected(True)
            self._current_model = current
    
    def _on_provider_clicked(self, provider_name: str):
        """Handle provider click."""
        self._current_provider = provider_name
        self._debug_print_selection()
        
        if self._current_model and self._current_provider:
            self.selection_changed.emit(self._current_model, self._current_provider)
    
    def _on_provider_star_toggled(self, provider_name: str, new_status: bool):
        """Handle provider star toggle."""
        if self._current_model:
            if new_status:
                self._storage.set_starred_provider(self._current_model, provider_name)
            else:
                self._storage.set_starred_provider(self._current_model, None)
    
    def _on_family_clicked(self, family_name: str):
        """Handle family click - scroll to family header and flash it."""
        header = self._family_headers.get(family_name)
        if header:
            # Scroll to header
            # Using ensureWidgetVisible works, but to make sure it's at top, we can manipulate scrollbar
            # However, ensureWidgetVisible with small margin is safer if we are near bottom
            self.model_scroll.ensureWidgetVisible(header, 0, 0)
            
            # Force alignment to top if possible
            # Get header position relative to container
            header_pos = header.y()
            self.model_scroll.verticalScrollBar().setValue(header_pos)
            
            # Flash effect
            header.flash()
    
    def _on_model_scroll(self):
        """Handle model list scroll - update family highlight."""
        # Find the topmost visible model card (using primary cards only)
        viewport_top = self.model_scroll.verticalScrollBar().value()
        
        for model_key, card in self._primary_model_cards.items():
            card_pos = card.mapTo(self.model_container, card.rect().topLeft())
            if card_pos.y() >= viewport_top - 20:
                # This is the first visible card
                family = self._model_to_family.get(model_key, "")
                self.family_list.set_highlighted_family(family)
                break
    
    def _on_ok_clicked(self):
        """Handle OK button click."""
        self.close_requested.emit()
    
    def _debug_print_selection(self):
        """Print debug info about current selection."""
        if not self._current_model or not self._current_provider:
            return
        
        provider_config = None
        try:
            model_data = self._models.get(self._current_model, {})
            provider_config = model_data.get('providers', {}).get(self._current_provider, {})
            
            # Handle edge cases: provider_config might be None, ellipsis (...), or non-dict
            if not isinstance(provider_config, dict):
                print(f"[ModelSelector] Warning: provider_config is not a dict: {type(provider_config).__name__} = {provider_config}")
                provider_config = {}
            
            # Get API info
            api_name = provider_config.get('api-name', self._current_model)
            api_scheme = model_data.get('api-scheme', 'unknown')
            
            # Get provider endpoint
            providers_global = self._config.get('api', {}).get('providers', {})
            provider_info = providers_global.get(self._current_provider, {})
            
            # Handle edge case: provider_info might be None or non-dict
            if not isinstance(provider_info, dict):
                print(f"[ModelSelector] Warning: provider_info is not a dict: {type(provider_info).__name__} = {provider_info}")
                provider_info = {}
            
            endpoint = provider_info.get('endpoint', 'unknown')
            
            print(f"[ModelSelector] Selected: model={self._current_model}, provider={self._current_provider}")
            print(f"[ModelSelector] API Info: endpoint={endpoint}, api-name={api_name}, scheme={api_scheme}")
        except Exception as e:
            print(f"[ModelSelector] Error fetching dict data: {e}")
            print(f"[ModelSelector] provider_config: {provider_config}")
            print(f"[ModelSelector] provider_config type: {type(provider_config).__name__}")
    
    def keyPressEvent(self, event):
        """Handle key press - ESC to close."""
        if event.key() == Qt.Key_Escape:
            self.close_requested.emit()
        super().keyPressEvent(event)
    
    def _is_in_resize_zone(self, pos: QPoint) -> bool:
        """Check if position is in the resize zone (right-bottom corner)."""
        rect = self.rect()
        # Check if in right edge or bottom edge zone
        in_right =  rect.width() - self._resize_margin <= pos.x() <= rect.width() + self._resize_margin
        in_bottom = rect.height() - self._resize_margin <= pos.y() <= rect.height() + self._resize_margin
        return in_right or in_bottom
    
    def _get_resize_direction(self, pos: QPoint) -> tuple:
        """Get resize direction as (horizontal, vertical) booleans."""
        rect = self.rect()
        in_right =  rect.width() - self._resize_margin <= pos.x() <= rect.width() + self._resize_margin
        in_bottom = rect.height() - self._resize_margin <= pos.y() <= rect.height() + self._resize_margin
        return (in_right, in_bottom)
    
    def mousePressEvent(self, event):
        """Handle mouse press for resize."""
        if event.button() == Qt.LeftButton and self._is_in_resize_zone(event.pos()):
            self._resize_dragging = True
            self._drag_start_pos = event.globalPos()
            self._drag_start_size = self.size()
            self._resize_direction = self._get_resize_direction(event.pos())
            event.accept()
        else:
            super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move for resize cursor and dragging."""
        if self._resize_dragging:
            # Calculate new size
            delta = event.globalPos() - self._drag_start_pos
            new_width = self._drag_start_size.width()
            new_height = self._drag_start_size.height()
            
            if self._resize_direction[0]:  # horizontal
                new_width = max(self.minimumWidth(), self._drag_start_size.width() + delta.x())
            if self._resize_direction[1]:  # vertical
                new_height = max(self.minimumHeight(), self._drag_start_size.height() + delta.y())
            
            self.resize(new_width, new_height)
            event.accept()
        else:
            # Update cursor based on position
            if self._is_in_resize_zone(event.pos()):
                h, v = self._get_resize_direction(event.pos())
                if h and v:
                    self.setCursor(Qt.SizeFDiagCursor)
                elif h:
                    self.setCursor(Qt.SizeHorCursor)
                elif v:
                    self.setCursor(Qt.SizeVerCursor)
            else:
                self.unsetCursor()
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release to end resize."""
        if event.button() == Qt.LeftButton and self._resize_dragging:
            self._resize_dragging = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)
    
    def resizeEvent(self, event):
        """Update resize grip position on resize."""
        super().resizeEvent(event)
        # Position grip at bottom-right corner
        self.resize_grip.move(
            self.width() - self.resize_grip.width() - 4,
            self.height() - self.resize_grip.height() - 4
        )
    
    def get_current_selection(self) -> tuple:
        """Get current selection as (model_key, provider_name)."""
        return (self._current_model, self._current_provider)
    
    def set_selection(self, model_key: str, provider_name: str) -> bool:
        """Set current selection. Returns True if successful."""
        if model_key not in self._models:
            return False
        
        self._select_model(model_key)
        
        model_data = self._models.get(model_key, {})
        providers_config = model_data.get('providers', {})
        
        # Handle edge case: providers_config might be None or non-dict
        if not isinstance(providers_config, dict):
            print(f"[ModelSelector] Warning: providers_config for model '{model_key}' is not a dict: {type(providers_config).__name__} = {providers_config}")
            return False
        
        providers = list(providers_config.keys())
        if provider_name not in providers:
            return False
        
        self.provider_list.select_provider(provider_name)
        self._current_provider = provider_name
        
        return True
