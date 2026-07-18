"""Reusable thinking-level combo for task cards and retry panels."""

from __future__ import annotations

from typing import List, Optional

from PyQt5.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

try:
    from chatbot_core.thinking_resolver import (
        SUPPORTED_NORMALIZED_LEVELS,
        get_task_default_thinking_level,
        load_root_config,
    )
except Exception:
    load_root_config = None
    get_task_default_thinking_level = None
    SUPPORTED_NORMALIZED_LEVELS = ("auto", "no", "yes", "low", "mid", "high")


class ThinkingLevelSelector(QWidget):
    """Labeled combo for normalized thinking levels (auto/no/yes/low/mid/high)."""

    def __init__(
        self,
        task_key: Optional[str] = None,
        show_label: bool = True,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.task_key = task_key or ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        if show_label:
            label = QLabel("Thinking:")
            label.setStyleSheet("color: #666666; font-size: 13px;")
            layout.addWidget(label)

        self.combo = QComboBox()
        self.combo.setObjectName("thinkingLevelCombo")
        self.combo.setStyleSheet("""
            QComboBox#thinkingLevelCombo {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 4px;
                padding: 2px 8px;
                min-width: 90px;
                font-size: 13px;
            }
            QComboBox#thinkingLevelCombo:hover {
                border-color: #b0b0b0;
            }
        """)
        layout.addWidget(self.combo)

        self.set_supported_levels(list(SUPPORTED_NORMALIZED_LEVELS))
        self.apply_default_level()

    def _combo_has_value(self, value: str) -> bool:
        for i in range(self.combo.count()):
            if self.combo.itemText(i) == value:
                return True
        return False

    def apply_default_level(self):
        """Initialize from config.yaml task default when available."""
        if load_root_config and get_task_default_thinking_level and self.task_key:
            try:
                root = load_root_config()
                default_level = get_task_default_thinking_level(root, self.task_key)
                if default_level:
                    if self._combo_has_value(default_level):
                        self.combo.setCurrentText(default_level)
                        return
                    if default_level in ("low", "mid", "high") and self._combo_has_value("yes"):
                        self.combo.setCurrentText("yes")
                        return
            except Exception:
                pass

        fallback = "low" if self.task_key == "assemble-sentence" else "auto"
        if self._combo_has_value(fallback):
            self.combo.setCurrentText(fallback)
        elif fallback in ("low", "mid", "high") and self._combo_has_value("yes"):
            self.combo.setCurrentText("yes")

    def get_thinking_level(self) -> str:
        return self.combo.currentText().strip() or "auto"

    def set_thinking_level(self, level: Optional[str]):
        if not level:
            return
        if self._combo_has_value(level):
            self.combo.setCurrentText(level)
        elif level in ("low", "mid", "high") and self._combo_has_value("yes"):
            self.combo.setCurrentText("yes")

    def set_supported_levels(self, levels: List[str]):
        """
        Update options. Prefer preserving the current selection when possible.
        """
        current = self.get_thinking_level() if self.combo.count() else None

        self.combo.blockSignals(True)
        try:
            self.combo.clear()
            for level in levels:
                self.combo.addItem(level)
            if current and self._combo_has_value(current):
                self.combo.setCurrentText(current)
            elif current in ("low", "mid", "high") and self._combo_has_value("yes"):
                self.combo.setCurrentText("yes")
            else:
                self.apply_default_level()
        finally:
            self.combo.blockSignals(False)
