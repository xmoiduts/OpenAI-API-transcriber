"""
Assemble Task Group Window - ultra-wide horizontal host for Assemble Sentence subtasks.

Layout:
  title
  horizontal-scrollable task cards
  bottom toolbar: Approve All | Merge Output | Close

Close with running tasks only hides the window (background continue).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PyQt5.QtCore import Qt, QEvent, QPoint, pyqtSignal
from PyQt5.QtGui import QFont, QPainter, QColor, QPen
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
    QFrame,
    QMessageBox,
    QApplication,
)

import sys

src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from .composite_retry_button import CompositeRetryButton
from .task_popup_window import TaskExecutionPanel
from ..flying_message import show_flying_message
from sentence_builder.assemble_output import (
    AssemblePart,
    AXIS_ORIGINAL_FILENAME,
    build_merged_text,
    strip_trailing_punctuation,
    write_axis_original_atomic,
)
from chatbot_core import ChatCore


CARD_WIDTH = 520


@dataclass
class AssembleSubtaskSpec:
    """Immutable-enough creation recipe so a card can be rebuilt in-place."""

    task_index: int
    line_range: Tuple[int, int]
    total: int
    needs_approval: bool
    max_line_length: float
    max_over_limit_pct: float
    prompt: str
    context_text: str
    thinking_level: Optional[str]
    model: Optional[str] = None
    provider: Optional[str] = None
    tier: str = "default"
    skip_auto_start: bool = False


class MergeOverviewPopup(QWidget):
    """Read-only hover overview of mergeability. Ignores mouse events."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(
            parent,
            Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._items: List[Tuple[int, Tuple[int, int], bool, bool]] = []
        # (task_index, line_range, mergeable, is_running)

        self.setStyleSheet(
            "background-color: #ffffff; border: 1px solid #b0b0b0; border-radius: 6px;"
        )

    def set_items(self, items: List[Tuple[int, Tuple[int, int], bool, bool]]):
        self._items = list(items)
        # Rough size: each tile ~70x48 + padding
        cols = min(8, max(1, len(self._items)))
        rows = max(1, (len(self._items) + cols - 1) // cols) if self._items else 1
        self.resize(16 + cols * 78, 16 + rows * 54)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        painter.setPen(QPen(QColor("#b0b0b0"), 1))
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)

        if not self._items:
            painter.setPen(QColor("#888888"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No tasks")
            return

        cols = min(8, max(1, len(self._items)))
        x0, y0 = 8, 8
        tw, th = 70, 46
        for i, (idx, lr, mergeable, running) in enumerate(self._items):
            col = i % cols
            row = i // cols
            x = x0 + col * (tw + 8)
            y = y0 + row * (th + 8)
            rect = (x, y, tw, th)

            if running:
                border = QColor("#f0a000")
                fill = QColor("#fff8e8")
            elif mergeable:
                border = QColor("#2e7d32")
                fill = QColor("#e8f5e9")
            else:
                border = QColor("#c62828")
                fill = QColor("#ffebee")

            painter.fillRect(x, y, tw, th, fill)
            painter.setPen(QPen(border, 2))
            painter.drawRect(x, y, tw - 1, th - 1)
            painter.setPen(QColor("#333333"))
            painter.drawText(
                x + 2,
                y + 2,
                tw - 4,
                th - 4,
                Qt.AlignCenter | Qt.TextWordWrap,
                f"#{idx}\n{lr[0]}-{lr[1]}",
            )


class AssembleSubtaskCard(QFrame):
    """One horizontally laid-out assemble subtask with extra action buttons."""

    status_changed = pyqtSignal(int, str)  # task_index, status
    stream_activity = pyqtSignal(int)
    mergeable_changed = pyqtSignal()
    retry_with_requested = pyqtSignal(object)  # AssembleSubtaskCard emitter via self

    def __init__(
        self,
        spec: AssembleSubtaskSpec,
        chat_core: ChatCore,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.spec = spec
        self.task_index = spec.task_index
        self.line_range = spec.line_range
        self.prompt = spec.prompt
        self.context_text = spec.context_text
        self.thinking_level = spec.thinking_level
        self.tier = spec.tier or "default"
        self._mergeable = False
        self._manual_mergeable: Optional[bool] = None  # None = use default from status

        self.setObjectName("assembleSubtaskCard")
        self.setFixedWidth(CARD_WIDTH)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame#assembleSubtaskCard {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        slice_info = (
            f"{spec.task_index}/{spec.total} "
            f"(lines {spec.line_range[0]}-{spec.line_range[1]})"
        )
        self.panel = TaskExecutionPanel(
            task_name="Assemble Sentence",
            line_range=spec.line_range,
            needs_approval=spec.needs_approval,
            slice_info=slice_info,
            enable_line_metrics=True,
            max_line_length=spec.max_line_length,
            max_over_limit_pct=spec.max_over_limit_pct,
            show_close_button=False,
            copy_button_label="Copy Part Output",
            compact_header=True,
        )
        self.panel.set_chat_core(chat_core)
        self.panel.set_context(spec.context_text)
        layout.addWidget(self.panel, 1)

        extra = QHBoxLayout()
        self.retry_control = CompositeRetryButton(
            applicable_task="text-chat",
            task_key="assemble-sentence",
        )
        self._sync_retry_seed()
        self.retry_control.retry_clicked.connect(self.retry)
        self.retry_control.retry_with_requested.connect(self._on_retry_with)
        extra.addWidget(self.retry_control)
        # Back-compat alias for tests / callers expecting retry_btn
        self.retry_btn = self.retry_control.retry_btn

        self.strip_punct_btn = QPushButton("Remove Trailing Punctuation")
        self.strip_punct_btn.clicked.connect(self._on_strip_punctuation)
        extra.addWidget(self.strip_punct_btn)

        self.mergeable_btn = QPushButton("Mergeable: No")
        self.mergeable_btn.setCheckable(True)
        self.mergeable_btn.setEnabled(False)
        self.mergeable_btn.clicked.connect(self._on_mergeable_toggled)
        extra.addWidget(self.mergeable_btn)
        extra.addStretch()
        layout.addLayout(extra)

        self.panel.task_completed.connect(self._on_completed)
        self.panel.gate_approved.connect(self._on_gate_approved)
        self.panel.stream_activity.connect(lambda _s: self.stream_activity.emit(self.task_index))
        self.panel.auto_quenched.connect(self._on_interrupted)
        self.panel.stopped.connect(self._on_interrupted)
        self._skip_auto_start = bool(spec.skip_auto_start)

    def _sync_retry_seed(self):
        core = self.panel.chat_core
        model = None
        provider = None
        if core is not None:
            model = core.get_current_model()
            provider = core.get_current_provider()
        if model is None:
            model = self.spec.model
        if provider is None:
            provider = self.spec.provider
        self.retry_control.set_seed_values(
            model=model,
            provider=provider,
            thinking_level=self.thinking_level,
            tier=self.tier,
            chat_core=core,
        )

    def mark_empty_error(self):
        """Mark this card as failed due to empty context; skip auto-start."""
        self._skip_auto_start = True
        self.spec.skip_auto_start = True
        self.panel._status = "error"
        self.panel.log("No data in specified range")
        self._apply_default_mergeable(False)
        self.status_changed.emit(self.task_index, "error")

    # ---- status / mergeable ----

    def status(self) -> str:
        return self.panel.status

    def is_running(self) -> bool:
        return self.panel.is_running()

    def is_waiting_approval(self) -> bool:
        return self.panel.is_waiting_approval()

    def effective_mergeable(self) -> bool:
        if self._manual_mergeable is not None:
            return self._manual_mergeable
        return self._mergeable

    def get_output_text(self) -> str:
        return self.panel.get_response_text()

    def current_model_provider(self) -> Tuple[Optional[str], Optional[str]]:
        core = self.panel.chat_core
        if core is None:
            return (self.spec.model, self.spec.provider)
        return (core.get_current_model(), core.get_current_provider())

    def _refresh_mergeable_ui(self):
        can_toggle = self._can_toggle_mergeable()
        self.mergeable_btn.setEnabled(can_toggle)
        on = self.effective_mergeable()
        self.mergeable_btn.blockSignals(True)
        self.mergeable_btn.setChecked(on)
        self.mergeable_btn.setText(f"Mergeable: {'Yes' if on else 'No'}")
        self.mergeable_btn.blockSignals(False)
        self.mergeable_changed.emit()

    def _can_toggle_mergeable(self) -> bool:
        st = self.panel.status
        if st in ("running", "waiting", "idle"):
            return False
        # Terminal states with some output may be toggled.
        return bool((self.panel.get_response_text() or "").strip()) or st == "success"

    def _apply_default_mergeable(self, success: bool):
        self._manual_mergeable = None
        self._mergeable = bool(success)
        self._refresh_mergeable_ui()

    def _on_mergeable_toggled(self, checked: bool):
        if not self._can_toggle_mergeable():
            self._refresh_mergeable_ui()
            return
        self._manual_mergeable = bool(checked)
        self._refresh_mergeable_ui()

    # ---- lifecycle ----

    def start_initial(self):
        if self._skip_auto_start:
            return
        self.panel.log(f"Slice {self.task_index}")
        self.panel.log(f"Context length: {len(self.context_text)} chars")
        self.panel.log(f"Prompt length: {len(self.prompt)} chars")
        if self.panel.needs_approval and not self.panel._is_approved:
            self.panel.log("Waiting for manual approval to proceed...")
            self.status_changed.emit(self.task_index, "untriggered")
        else:
            self.panel.log("Auto-approved (first slice)")
            self.status_changed.emit(self.task_index, "running")
        self.panel.execute_prompt(
            self.prompt,
            thinking_level=self.thinking_level,
            task_key="assemble-sentence",
        )

    def approve(self):
        if self.is_waiting_approval():
            self.panel.approve_and_start()

    def stop(self):
        if self.is_running() or self.panel.status == "running":
            self.panel.request_stop()
            self.status_changed.emit(self.task_index, "interrupted")
            self._apply_default_mergeable(False)

    def dispose(self):
        """Stop any worker and detach so the widget can be replaced safely."""
        try:
            self.panel.clear_runtime_state()
        except Exception:
            pass
        self.setParent(None)

    def retry(self):
        self._manual_mergeable = None
        self._mergeable = False
        self.panel.clear_runtime_state()
        # Retry bypasses approval gate
        self.panel.needs_approval = False
        self.panel._is_approved = True
        if self.panel.approve_button:
            self.panel.approve_button.setEnabled(False)
            self.panel.approve_button.setText("✓ Approved")
        self.status_changed.emit(self.task_index, "running")
        self.panel.log(f"Retrying lines {self.line_range[0]}-{self.line_range[1]}")
        self.panel.execute_prompt(
            self.prompt,
            thinking_level=self.thinking_level,
            task_key="assemble-sentence",
            force=True,
        )
        self._sync_retry_seed()
        self._refresh_mergeable_ui()

    def apply_thinking_and_retry(self, thinking_level: Optional[str], tier: str = "default"):
        """Reuse this card with updated thinking/tier (no model change)."""
        self.thinking_level = thinking_level
        self.spec.thinking_level = thinking_level
        self.tier = tier or "default"
        self.spec.tier = self.tier
        self._sync_retry_seed()
        self.retry()

    def _on_retry_with(self, model: str, provider: str, thinking: str, tier: str):
        # Bubble to group; include self so group can decide recreate vs reuse.
        self._pending_retry_with = (model, provider, thinking, tier)
        self.retry_with_requested.emit(self)

    def take_pending_retry_with(self) -> Optional[Tuple[str, str, str, str]]:
        pending = getattr(self, "_pending_retry_with", None)
        self._pending_retry_with = None
        return pending

    def _on_strip_punctuation(self):
        text = self.panel.get_response_text()
        if not text:
            return
        cleaned = strip_trailing_punctuation(text)
        self.panel.set_response_text(cleaned)
        self.panel.log("Trailing punctuation removed from part output.")

    def _on_completed(self, success: bool, _response: str):
        status = "success" if success else "error"
        self.status_changed.emit(self.task_index, status)
        self._apply_default_mergeable(success)

    def _on_gate_approved(self):
        self.status_changed.emit(self.task_index, "running")

    def _on_interrupted(self):
        self.status_changed.emit(self.task_index, "interrupted")
        self._apply_default_mergeable(False)


class AssembleTaskGroupWindow(QDialog):
    """Task group: Assemble Sentence — hosts all subtask cards in one window."""

    task_status_changed = pyqtSignal(tuple, str)  # line_range, status
    task_stream_activity = pyqtSignal(tuple)  # line_range
    closed_to_background = pyqtSignal()

    def __init__(
        self,
        run_id: int,
        result_dir: Path,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.run_id = run_id
        self.result_dir = Path(result_dir)
        self._cards: Dict[int, AssembleSubtaskCard] = {}  # task_index -> card
        self._cards_by_range: Dict[Tuple[int, int], AssembleSubtaskCard] = {}
        self._overview = MergeOverviewPopup(None)

        self.setWindowTitle("Task group: Assemble Sentence")
        self.setModal(False)
        self.setMinimumSize(800, 500)

        self._init_ui()
        self._size_to_screen()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        title = QLabel("Task group: Assemble Sentence")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        title.setFont(font)
        title.setStyleSheet("color: #333333; border-bottom: 2px solid #4CAF50; padding-bottom: 6px;")
        layout.addWidget(title)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background-color: #f7f7f7;
            }
        """)

        self.cards_host = QWidget()
        self.cards_layout = QHBoxLayout(self.cards_host)
        self.cards_layout.setContentsMargins(8, 8, 8, 8)
        self.cards_layout.setSpacing(12)
        self.cards_layout.addStretch(1)
        self.scroll.setWidget(self.cards_host)
        layout.addWidget(self.scroll, 1)

        toolbar = QHBoxLayout()
        self.approve_all_btn = QPushButton("Approve All")
        self.approve_all_btn.setObjectName("approveAllButton")
        self.approve_all_btn.clicked.connect(self.approve_all)
        toolbar.addWidget(self.approve_all_btn)

        self.merge_btn = QPushButton("Merge Output")
        self.merge_btn.setObjectName("mergeButton")
        self.merge_btn.clicked.connect(self.merge_output)
        self.merge_btn.installEventFilter(self)
        toolbar.addWidget(self.merge_btn)

        toolbar.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.setObjectName("closeButton")
        self.close_btn.clicked.connect(self._on_close_clicked)
        toolbar.addWidget(self.close_btn)
        layout.addLayout(toolbar)

        self.setStyleSheet("""
            QDialog { background-color: #ffffff; }
            QPushButton#approveAllButton {
                background-color: #4CAF50; color: white; border: none;
                border-radius: 4px; padding: 8px 18px; font-weight: bold;
            }
            QPushButton#approveAllButton:hover { background-color: #45a049; }
            QPushButton#mergeButton {
                background-color: #1976d2; color: white; border: none;
                border-radius: 4px; padding: 8px 18px; font-weight: bold;
            }
            QPushButton#mergeButton:hover { background-color: #1565c0; }
            QPushButton#mergeButton:disabled { background-color: #90caf9; }
            QPushButton#closeButton {
                background-color: #666666; color: white; border: none;
                border-radius: 4px; padding: 8px 18px; font-weight: bold;
            }
            QPushButton#closeButton:hover { background-color: #555555; }
        """)

    def _size_to_screen(self):
        screen = QApplication.primaryScreen()
        if screen is None:
            self.resize(1200, 700)
            return
        geo = screen.availableGeometry()
        w = int(geo.width() * 0.60)
        h = int(geo.height() * 0.60)
        self.resize(max(800, w), max(500, h))
        self.move(
            geo.x() + (geo.width() - self.width()) // 2,
            geo.y() + (geo.height() - self.height()) // 2,
        )

    # ---- card management ----

    def add_subtask(
        self,
        task_index: int,
        line_range: Tuple[int, int],
        total: int,
        needs_approval: bool,
        max_line_length: float,
        max_over_limit_pct: float,
        chat_core: ChatCore,
        prompt: str,
        context_text: str,
        thinking_level: Optional[str],
        *,
        skip_auto_start: bool = False,
        tier: str = "default",
    ) -> AssembleSubtaskCard:
        model = chat_core.get_current_model() if chat_core else None
        provider = chat_core.get_current_provider() if chat_core else None
        spec = AssembleSubtaskSpec(
            task_index=task_index,
            line_range=line_range,
            total=total,
            needs_approval=needs_approval,
            max_line_length=max_line_length,
            max_over_limit_pct=max_over_limit_pct,
            prompt=prompt,
            context_text=context_text,
            thinking_level=thinking_level,
            model=model,
            provider=provider,
            tier=tier,
            skip_auto_start=skip_auto_start,
        )
        return self._insert_card(spec, chat_core, layout_index=None)

    def _insert_card(
        self,
        spec: AssembleSubtaskSpec,
        chat_core: ChatCore,
        layout_index: Optional[int],
    ) -> AssembleSubtaskCard:
        card = AssembleSubtaskCard(
            spec=spec,
            chat_core=chat_core,
            parent=self.cards_host,
        )
        if layout_index is None:
            # Insert before trailing stretch
            stretch_idx = self.cards_layout.count() - 1
            self.cards_layout.insertWidget(stretch_idx, card)
        else:
            self.cards_layout.insertWidget(layout_index, card)

        self._cards[spec.task_index] = card
        self._cards_by_range[spec.line_range] = card

        card.status_changed.connect(self._on_card_status)
        card.stream_activity.connect(self._on_card_stream)
        card.mergeable_changed.connect(self._update_merge_enabled)
        card.retry_with_requested.connect(self._on_card_retry_with)
        return card

    def _create_chat_core_for_spec(self, spec: AssembleSubtaskSpec, system_prompt: Optional[str] = None) -> ChatCore:
        core = ChatCore(system_prompt=system_prompt)
        if spec.model and spec.provider:
            core.set_model(spec.model, spec.provider)
        return core

    def replace_subtask_same_slot(
        self,
        old_card: AssembleSubtaskCard,
        *,
        model: str,
        provider: str,
        thinking_level: Optional[str],
        tier: str = "default",
        auto_retry: bool = True,
    ) -> AssembleSubtaskCard:
        """
        Destroy old_card and recreate at the same layout index / task ordering.

        Used when Retry-with selects a different model/provider.
        """
        layout_index = self.cards_layout.indexOf(old_card)
        if layout_index < 0:
            layout_index = None

        spec = AssembleSubtaskSpec(
            task_index=old_card.spec.task_index,
            line_range=old_card.spec.line_range,
            total=old_card.spec.total,
            needs_approval=False,  # retry path bypasses approval
            max_line_length=old_card.spec.max_line_length,
            max_over_limit_pct=old_card.spec.max_over_limit_pct,
            prompt=old_card.spec.prompt,
            context_text=old_card.spec.context_text,
            thinking_level=thinking_level,
            model=model,
            provider=provider,
            tier=tier or "default",
            skip_auto_start=False,
        )

        # Snapshot system prompt from old core if available
        system_prompt = None
        if old_card.panel.chat_core is not None:
            try:
                system_prompt = old_card.panel.chat_core.get_system_prompt()
            except Exception:
                system_prompt = None

        old_card.dispose()
        # Remove from layout/maps before the async delete finishes
        if layout_index is not None and self.cards_layout.indexOf(old_card) >= 0:
            self.cards_layout.removeWidget(old_card)
        self._cards.pop(old_card.task_index, None)
        self._cards_by_range.pop(old_card.line_range, None)
        old_card.deleteLater()

        chat_core = self._create_chat_core_for_spec(spec, system_prompt=system_prompt)
        new_card = self._insert_card(spec, chat_core, layout_index=layout_index)

        if auto_retry:
            # Immediate retry (no approval gate)
            new_card.retry()
        self._update_merge_enabled()
        return new_card

    def _on_card_retry_with(self, card: AssembleSubtaskCard):
        pending = card.take_pending_retry_with()
        if not pending:
            return
        model, provider, thinking, tier = pending
        cur_model, cur_provider = card.current_model_provider()
        model_changed = (model != cur_model) or (provider != cur_provider)

        if model_changed:
            self.replace_subtask_same_slot(
                card,
                model=model,
                provider=provider,
                thinking_level=thinking,
                tier=tier,
                auto_retry=True,
            )
        else:
            # Thinking / tier only — reuse widget; tier is mock (not sent to provider)
            card.apply_thinking_and_retry(thinking, tier=tier)

    def start_all_initial(self):
        for idx in sorted(self._cards.keys()):
            self._cards[idx].start_initial()
        self._update_merge_enabled()

    def approve_all(self):
        for card in self._cards.values():
            if card.is_waiting_approval():
                card.approve()
        self._update_merge_enabled()

    def has_running_tasks(self) -> bool:
        return any(c.is_running() for c in self._cards.values())

    def focus_line_range(self, line_range: Tuple[int, int]):
        card = self._cards_by_range.get(line_range)
        if not card:
            return
        self.show()
        self.raise_()
        self.activateWindow()
        # Scroll horizontally so the card is visible
        self.scroll.ensureWidgetVisible(card, 40, 40)

    def get_card(self, line_range: Tuple[int, int]) -> Optional[AssembleSubtaskCard]:
        return self._cards_by_range.get(line_range)

    def stop_line_range(self, line_range: Tuple[int, int]):
        card = self._cards_by_range.get(line_range)
        if card:
            card.stop()

    def retry_line_range(self, line_range: Tuple[int, int]):
        card = self._cards_by_range.get(line_range)
        if card:
            card.retry()

    def start_line_range(self, line_range: Tuple[int, int]):
        """Approve/start a waiting card, or retry if already terminal."""
        card = self._cards_by_range.get(line_range)
        if not card:
            return
        if card.is_waiting_approval():
            card.approve()
        elif not card.is_running():
            card.retry()

    # ---- signals from cards ----

    def _on_card_status(self, task_index: int, status: str):
        card = self._cards.get(task_index)
        if not card:
            return
        self.task_status_changed.emit(card.line_range, status)
        self._update_merge_enabled()

    def _on_card_stream(self, task_index: int):
        card = self._cards.get(task_index)
        if card:
            self.task_stream_activity.emit(card.line_range)

    def _update_merge_enabled(self):
        running = self.has_running_tasks()
        self.merge_btn.setEnabled(not running and bool(self._cards))
        if running:
            self.merge_btn.setToolTip("Cannot merge while tasks are still running")
        else:
            self.merge_btn.setToolTip("Merge outputs into 句轴原文.txt")

    # ---- merge ----

    def _overview_items(self):
        items = []
        for idx in sorted(self._cards.keys()):
            card = self._cards[idx]
            items.append(
                (
                    idx,
                    card.line_range,
                    card.effective_mergeable(),
                    card.is_running(),
                )
            )
        return items

    def eventFilter(self, obj, event):
        if obj is self.merge_btn:
            if event.type() == QEvent.Enter:
                self._show_overview()
            elif event.type() in (QEvent.Leave, QEvent.MouseButtonPress):
                self._hide_overview()
        return super().eventFilter(obj, event)

    def _show_overview(self):
        self._overview.set_items(self._overview_items())
        pos = self.merge_btn.mapToGlobal(QPoint(0, self.merge_btn.height() + 4))
        self._overview.move(pos)
        self._overview.show()
        self._overview.raise_()

    def _hide_overview(self):
        self._overview.hide()

    def merge_output(self):
        if self.has_running_tasks():
            show_flying_message(self, "Cannot merge while tasks are still running")
            return
        if not self._cards:
            return

        parts = []
        for idx in sorted(self._cards.keys()):
            card = self._cards[idx]
            parts.append(
                AssemblePart(
                    task_index=idx,
                    line_range=card.line_range,
                    text=card.get_output_text() or "",
                    mergeable=card.effective_mergeable(),
                )
            )
        content = build_merged_text(parts)
        target = self.result_dir / AXIS_ORIGINAL_FILENAME

        if target.exists():
            reply = QMessageBox.question(
                self,
                "Overwrite 句轴原文.txt?",
                f"{target}\n\nFile already exists. Overwrite?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        try:
            write_axis_original_atomic(self.result_dir, content)
            show_flying_message(self, f"Merged to {AXIS_ORIGINAL_FILENAME}")
        except Exception as e:
            QMessageBox.critical(self, "Merge failed", str(e))
            show_flying_message(self, f"Merge failed: {e}")

    # ---- close / background ----

    def _on_close_clicked(self):
        self.close()

    def closeEvent(self, event):
        self._hide_overview()
        if self.has_running_tasks():
            show_flying_message(self, "Task running in background")
            self.closed_to_background.emit()
            # Hide instead of destroy — keep workers alive
            event.ignore()
            self.hide()
            return
        # No running tasks: still keep the window object (dangling policy),
        # but allow hide via accept+hide so user can reopen via magnifier.
        event.ignore()
        self.hide()

    def reject(self):
        # Esc / system close → same as Close
        self.close()
