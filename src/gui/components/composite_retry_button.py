"""
Composite Retry button: main Retry + chevron that opens a Retry-with panel.

Layout of options popup:
  row1: model selector | thinking level | tier (mock)
  row2: Retry button
"""

from __future__ import annotations

from typing import Optional, Tuple

from PyQt5.QtCore import QEvent, QPoint, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .model_selector import ModelSelectorWidget
from .thinking_level_selector import ThinkingLevelSelector

try:
    from chatbot_core.thinking_resolver import resolve_thinking
except Exception:
    resolve_thinking = None


MOCK_TIERS = ("default", "fast", "flex")


class RetryWithPopup(QFrame):
    """Anchored options panel for Retry with..."""

    retry_requested = pyqtSignal(str, str, str, str)  # model, provider, thinking, tier
    closed = pyqtSignal()

    def __init__(
        self,
        applicable_task: str = "text-chat",
        task_key: str = "assemble-sentence",
        parent: Optional[QWidget] = None,
    ):
        # Use Tool (not Popup) so the nested ModelSelectorWidget popup can open
        # without auto-dismissing this panel.
        super().__init__(parent, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setObjectName("retryWithPopup")
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self._task_key = task_key
        self._chat_core_for_resolve = None  # optional ChatCore for thinking refresh

        self.setStyleSheet("""
            QFrame#retryWithPopup {
                background-color: #ffffff;
                border: 1px solid #b0b0b0;
                border-radius: 6px;
            }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(10)

        row1 = QHBoxLayout()
        row1.setSpacing(8)

        self.model_selector = ModelSelectorWidget(
            applicable_task=applicable_task,
            max_popup_height=320,
        )
        # Compact for inline panel
        self.model_selector.trigger_button.setStyleSheet("""
            QPushButton#modelSelectorButton {
                background-color: #ffffff;
                color: #333333;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 4px 10px;
                text-align: left;
                font-size: 12px;
                min-width: 140px;
            }
            QPushButton#modelSelectorButton:hover {
                background-color: #f7f7f7;
                border-color: #b0b0b0;
            }
        """)
        self.model_selector.selection_confirmed.connect(self._on_model_confirmed)
        row1.addWidget(self.model_selector)

        self.thinking_selector = ThinkingLevelSelector(
            task_key=task_key,
            show_label=True,
        )
        row1.addWidget(self.thinking_selector)

        tier_box = QWidget()
        tier_layout = QHBoxLayout(tier_box)
        tier_layout.setContentsMargins(0, 0, 0, 0)
        tier_layout.setSpacing(6)
        tier_label = QLabel("Tier:")
        tier_label.setStyleSheet("color: #666666; font-size: 13px;")
        tier_layout.addWidget(tier_label)
        self.tier_combo = QComboBox()
        self.tier_combo.setObjectName("mockTierCombo")
        self.tier_combo.setStyleSheet("""
            QComboBox#mockTierCombo {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 2px 8px;
                min-width: 90px;
                font-size: 13px;
            }
            QComboBox#mockTierCombo:hover {
                border-color: #b0b0b0;
            }
        """)
        for t in MOCK_TIERS:
            self.tier_combo.addItem(t)
        tier_layout.addWidget(self.tier_combo)
        row1.addWidget(tier_box)

        root.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addStretch()
        self.retry_btn = QPushButton("Retry")
        self.retry_btn.setObjectName("retryWithConfirmButton")
        self.retry_btn.setCursor(Qt.PointingHandCursor)
        self.retry_btn.setStyleSheet("""
            QPushButton#retryWithConfirmButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 18px;
                font-weight: bold;
            }
            QPushButton#retryWithConfirmButton:hover {
                background-color: #45a049;
            }
        """)
        self.retry_btn.clicked.connect(self._on_confirm_retry)
        row2.addWidget(self.retry_btn)
        root.addLayout(row2)

    def set_initial_values(
        self,
        model: Optional[str],
        provider: Optional[str],
        thinking_level: Optional[str],
        tier: str = "default",
        chat_core=None,
    ):
        self._chat_core_for_resolve = chat_core
        if model and provider:
            self.model_selector.set_selection(model, provider)
            self._refresh_thinking_for_model(model, provider, chat_core)
        if thinking_level:
            self.thinking_selector.set_thinking_level(thinking_level)
        if tier in MOCK_TIERS:
            self.tier_combo.setCurrentText(tier)
        else:
            self.tier_combo.setCurrentText("default")

    def _on_model_confirmed(self, model: str, provider: str):
        self._refresh_thinking_for_model(model, provider, self._chat_core_for_resolve)

    def _refresh_thinking_for_model(self, model: str, provider: str, chat_core=None):
        if resolve_thinking is None:
            return
        cfg = None
        if chat_core is not None:
            try:
                # Prefer resolved config if the core already matches
                if (
                    chat_core.get_current_model() == model
                    and chat_core.get_current_provider() == provider
                ):
                    cfg = chat_core.get_current_config()
            except Exception:
                cfg = None
        if cfg is None and chat_core is not None:
            # Temporarily resolve via a throwaway set if needed — avoid mutating.
            # Fall back: use ModelResolver through ChatCore clone path is heavy;
            # try chat_core resolver via set_model on a throwaway is too invasive.
            pass
        if cfg is None:
            try:
                from chatbot_core.model_resolver import ModelResolver

                resolver = ModelResolver()
                cfg = resolver.resolve(model, provider)
            except Exception:
                return
        if not cfg:
            return
        try:
            res = resolve_thinking(cfg, None, task_key=self._task_key)
            self.thinking_selector.set_supported_levels(res.ui_supported_levels)
        except Exception:
            pass

    def _on_confirm_retry(self):
        model, provider = self.model_selector.get_current_selection()
        if not model or not provider:
            return
        thinking = self.thinking_selector.get_thinking_level()
        tier = self.tier_combo.currentText().strip() or "default"
        self.retry_requested.emit(model, provider, thinking, tier)
        self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)

    def hideEvent(self, event):
        self.closed.emit()
        super().hideEvent(event)


class CompositeRetryButton(QWidget):
    """
    Split button:

        |    Retry     |  v  |

    - Click Retry → retry_clicked
    - Hover chevron → Retry label becomes "Retry with..."
    - Click chevron → opens RetryWithPopup
    - Confirm in popup → retry_with_requested(model, provider, thinking, tier)
    """

    retry_clicked = pyqtSignal()
    retry_with_requested = pyqtSignal(str, str, str, str)  # model, provider, thinking, tier

    def __init__(
        self,
        applicable_task: str = "text-chat",
        task_key: str = "assemble-sentence",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("compositeRetryButton")
        self._applicable_task = applicable_task
        self._task_key = task_key
        self._popup: Optional[RetryWithPopup] = None
        self._seed_model: Optional[str] = None
        self._seed_provider: Optional[str] = None
        self._seed_thinking: Optional[str] = None
        self._seed_tier: str = "default"
        self._seed_chat_core = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.retry_btn = QPushButton("Retry")
        self.retry_btn.setObjectName("compositeRetryMain")
        self.retry_btn.setCursor(Qt.PointingHandCursor)
        self.retry_btn.clicked.connect(self._on_main_retry)
        self.retry_btn.setStyleSheet("""
            QPushButton#compositeRetryMain {
                background-color: #e8e8e8;
                color: #333333;
                border: 1px solid #d0d0d0;
                border-top-left-radius: 4px;
                border-bottom-left-radius: 4px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
                padding: 4px 12px;
                font-size: 11px;
                min-height: 22px;
            }
            QPushButton#compositeRetryMain:hover {
                background-color: #d8d8d8;
            }
            QPushButton#compositeRetryMain:pressed {
                background-color: #c8c8c8;
            }
        """)

        self.chevron_btn = QPushButton("v")
        self.chevron_btn.setObjectName("compositeRetryChevron")
        self.chevron_btn.setCursor(Qt.PointingHandCursor)
        self.chevron_btn.setFixedWidth(22)
        self.chevron_btn.clicked.connect(self._toggle_popup)
        self.chevron_btn.installEventFilter(self)
        self.chevron_btn.setStyleSheet("""
            QPushButton#compositeRetryChevron {
                background-color: #e8e8e8;
                color: #333333;
                border: 1px solid #d0d0d0;
                border-left: none;
                border-top-left-radius: 0px;
                border-bottom-left-radius: 0px;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
                padding: 4px 2px;
                font-size: 10px;
                font-weight: bold;
                min-height: 22px;
            }
            QPushButton#compositeRetryChevron:hover {
                background-color: #d8d8d8;
            }
            QPushButton#compositeRetryChevron:pressed {
                background-color: #c8c8c8;
            }
        """)

        layout.addWidget(self.retry_btn)
        layout.addWidget(self.chevron_btn)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def eventFilter(self, obj, event):
        if obj is self.chevron_btn:
            if event.type() == QEvent.Enter:
                self.retry_btn.setText("Retry with...")
            elif event.type() == QEvent.Leave:
                # Keep "Retry with..." while popup is open
                if not (self._popup and self._popup.isVisible()):
                    self.retry_btn.setText("Retry")
        return super().eventFilter(obj, event)

    def _on_main_retry(self):
        if self._popup and self._popup.isVisible():
            self._popup.hide()
        self.retry_btn.setText("Retry")
        self.retry_clicked.emit()

    def set_seed_values(
        self,
        model: Optional[str],
        provider: Optional[str],
        thinking_level: Optional[str],
        tier: str = "default",
        chat_core=None,
    ):
        """Values shown when the options popup opens."""
        self._seed_model = model
        self._seed_provider = provider
        self._seed_thinking = thinking_level
        self._seed_tier = tier or "default"
        self._seed_chat_core = chat_core

    def _ensure_popup(self) -> RetryWithPopup:
        if self._popup is None:
            self._popup = RetryWithPopup(
                applicable_task=self._applicable_task,
                task_key=self._task_key,
                parent=None,
            )
            self._popup.retry_requested.connect(self._on_popup_retry)
            self._popup.closed.connect(self._on_popup_closed)
        return self._popup

    def _on_popup_closed(self):
        if not (self.chevron_btn.underMouse()):
            self.retry_btn.setText("Retry")

    def _toggle_popup(self):
        popup = self._ensure_popup()
        if popup.isVisible():
            popup.hide()
            self.retry_btn.setText("Retry")
            return

        popup.set_initial_values(
            self._seed_model,
            self._seed_provider,
            self._seed_thinking,
            self._seed_tier,
            self._seed_chat_core,
        )

        # Prefer below the chevron
        anchor = self.chevron_btn.mapToGlobal(QPoint(0, self.chevron_btn.height() + 2))
        screen = QApplication.screenAt(anchor)
        if screen is None:
            screen = QApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else None

        popup.adjustSize()
        x = anchor.x() - popup.width() + self.chevron_btn.width()
        y = anchor.y()
        if geo is not None:
            if x < geo.left():
                x = geo.left() + 4
            if x + popup.width() > geo.right():
                x = geo.right() - popup.width() - 4
            if y + popup.height() > geo.bottom():
                # show above
                y = self.chevron_btn.mapToGlobal(QPoint(0, 0)).y() - popup.height() - 2
        popup.move(x, y)
        popup.show()
        popup.raise_()
        self.retry_btn.setText("Retry with...")

    def _on_popup_retry(self, model: str, provider: str, thinking: str, tier: str):
        self.retry_btn.setText("Retry")
        self.retry_with_requested.emit(model, provider, thinking, tier)

    def get_current_seed(self) -> Tuple[Optional[str], Optional[str], Optional[str], str]:
        return (
            self._seed_model,
            self._seed_provider,
            self._seed_thinking,
            self._seed_tier,
        )
