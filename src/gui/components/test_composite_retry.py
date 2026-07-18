"""Focused tests for composite Retry UI and assemble card replacement."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Optional, Tuple
from unittest.mock import MagicMock

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from PyQt5.QtCore import QEvent
from PyQt5.QtWidgets import QApplication, QWidget

from gui.components.assemble_task_group_window import (
    AssembleSubtaskCard,
    AssembleSubtaskSpec,
    AssembleTaskGroupWindow,
)
from gui.components.composite_retry_button import CompositeRetryButton, MOCK_TIERS


_APP = None


def _ensure_app() -> QApplication:
    global _APP
    app = QApplication.instance()
    if app is None:
        _APP = QApplication([])
    else:
        _APP = app
    return _APP


def _fake_chat_core(model: str = "model-a", provider: str = "provider-a"):
    core = MagicMock()
    core.get_current_model.return_value = model
    core.get_current_provider.return_value = provider
    core.get_system_prompt.return_value = "sys"
    core.get_current_config.return_value = None
    return core


class TestCompositeRetryButton(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_app()

    def setUp(self):
        self.host = QWidget()
        self.btn = CompositeRetryButton(parent=self.host)
        self.host.show()

    def tearDown(self):
        if self.btn._popup is not None:
            self.btn._popup.hide()
            self.btn._popup.deleteLater()
        self.host.close()
        self.host.deleteLater()
        QApplication.processEvents()

    def test_main_retry_emits(self):
        seen = []
        self.btn.retry_clicked.connect(lambda: seen.append(True))
        self.btn.retry_btn.click()
        self.assertEqual(seen, [True])
        self.assertEqual(self.btn.retry_btn.text(), "Retry")

    def test_chevron_hover_changes_label(self):
        self.assertEqual(self.btn.retry_btn.text(), "Retry")
        enter = QEvent(QEvent.Enter)
        QApplication.sendEvent(self.btn.chevron_btn, enter)
        self.assertEqual(self.btn.retry_btn.text(), "Retry with...")
        leave = QEvent(QEvent.Leave)
        QApplication.sendEvent(self.btn.chevron_btn, leave)
        self.assertEqual(self.btn.retry_btn.text(), "Retry")

    def test_mock_tiers_available(self):
        popup = self.btn._ensure_popup()
        items = [popup.tier_combo.itemText(i) for i in range(popup.tier_combo.count())]
        self.assertEqual(tuple(items), MOCK_TIERS)


class TestAssembleReplaceSameSlot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ensure_app()

    def setUp(self):
        self.group = AssembleTaskGroupWindow(run_id=1, result_dir=Path("."), parent=None)

    def tearDown(self):
        self.group.hide()
        self.group.deleteLater()
        QApplication.processEvents()

    def _add_card(self, index: int, model: str = "model-a", provider: str = "provider-a"):
        core = _fake_chat_core(model, provider)
        return self.group.add_subtask(
            task_index=index,
            line_range=(index * 10 + 1, index * 10 + 10),
            total=3,
            needs_approval=True,
            max_line_length=50.0,
            max_over_limit_pct=12.5,
            chat_core=core,
            prompt=f"prompt-{index}",
            context_text=f"ctx-{index}",
            thinking_level="low",
        )

    def test_model_change_detection_and_same_slot_order(self):
        c1 = self._add_card(1)
        c2 = self._add_card(2)
        c3 = self._add_card(3)

        order_before = [
            self.group.cards_layout.itemAt(i).widget()
            for i in range(self.group.cards_layout.count() - 1)
        ]
        self.assertEqual(order_before, [c1, c2, c3])

        layout_idx = self.group.cards_layout.indexOf(c2)
        self.assertEqual(layout_idx, 1)

        # Patch ChatCore construction used during replace
        created = []

        def _factory(spec, system_prompt=None):
            core = _fake_chat_core(spec.model, spec.provider)
            created.append((spec.model, spec.provider, spec.thinking_level, spec.tier))
            return core

        self.group._create_chat_core_for_spec = _factory  # type: ignore

        # Avoid starting a real LLM worker during auto_retry
        original_retry = AssembleSubtaskCard.retry
        calls = []

        def _noop_retry(self_card):
            calls.append(
                (
                    self_card.task_index,
                    self_card.spec.model,
                    self_card.thinking_level,
                    self_card.tier,
                )
            )
            self_card.status_changed.emit(self_card.task_index, "running")

        AssembleSubtaskCard.retry = _noop_retry  # type: ignore
        try:
            new_c2 = self.group.replace_subtask_same_slot(
                c2,
                model="model-b",
                provider="provider-b",
                thinking_level="high",
                tier="fast",
                auto_retry=True,
            )
        finally:
            AssembleSubtaskCard.retry = original_retry  # type: ignore

        order_after = [
            self.group.cards_layout.itemAt(i).widget()
            for i in range(self.group.cards_layout.count() - 1)
        ]
        self.assertEqual(len(order_after), 3)
        self.assertIs(order_after[0], c1)
        self.assertIs(order_after[2], c3)
        self.assertIs(order_after[1], new_c2)
        self.assertIsNot(new_c2, c2)
        self.assertEqual(new_c2.task_index, 2)
        self.assertEqual(new_c2.line_range, (21, 30))
        self.assertEqual(new_c2.spec.model, "model-b")
        self.assertEqual(new_c2.spec.provider, "provider-b")
        self.assertEqual(new_c2.thinking_level, "high")
        self.assertEqual(new_c2.tier, "fast")
        self.assertEqual(calls, [(2, "model-b", "high", "fast")])
        self.assertEqual(created, [("model-b", "provider-b", "high", "fast")])

        # Maps updated
        self.assertIs(self.group.get_card((21, 30)), new_c2)
        self.assertIs(self.group._cards[2], new_c2)

    def test_same_model_reuses_card_via_retry_with_handler(self):
        card = self._add_card(1)
        applied = []

        def _capture(thinking, tier="default"):
            applied.append((thinking, tier))

        card.apply_thinking_and_retry = _capture  # type: ignore
        card._pending_retry_with = ("model-a", "provider-a", "mid", "flex")
        self.group._on_card_retry_with(card)
        self.assertEqual(applied, [("mid", "flex")])
        # Still same instance in maps
        self.assertIs(self.group.get_card(card.line_range), card)

    def test_tier_not_required_on_spec_defaults(self):
        card = self._add_card(1)
        self.assertEqual(card.tier, "default")
        self.assertIn(card.tier, MOCK_TIERS)


class TestModelChangePredicate(unittest.TestCase):
    def test_detects_model_or_provider_change(self):
        def changed(cur: Tuple[Optional[str], Optional[str]], new: Tuple[str, str]) -> bool:
            return (new[0] != cur[0]) or (new[1] != cur[1])

        self.assertTrue(changed(("a", "p"), ("b", "p")))
        self.assertTrue(changed(("a", "p"), ("a", "q")))
        self.assertFalse(changed(("a", "p"), ("a", "p")))


if __name__ == "__main__":
    unittest.main()
