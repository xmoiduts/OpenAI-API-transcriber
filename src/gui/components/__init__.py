"""
GUI Components - Reusable PyQt5 widgets for the transcriber application.
"""

from .model_selector import ModelSelectorWidget
from .task_card import TaskCard, MergeOverlapsCard, CutpointCard, AssembleCard
from .task_popup_window import TaskPopupWindow, CollapsibleSection, TaskExecutionPanel
from .assemble_task_group_window import AssembleTaskGroupWindow
from .composite_retry_button import CompositeRetryButton
from .thinking_level_selector import ThinkingLevelSelector

# Chat sidebar backup (preserved for future use)
# from .chat_sidebar_backup import ChatSidebarPanel

__all__ = [
    'ModelSelectorWidget',
    'TaskCard',
    'MergeOverlapsCard',
    'CutpointCard',
    'AssembleCard',
    'TaskPopupWindow',
    'TaskExecutionPanel',
    'CollapsibleSection',
    'AssembleTaskGroupWindow',
    'CompositeRetryButton',
    'ThinkingLevelSelector',
]
