"""
GUI Components - Reusable PyQt5 widgets for the transcriber application.
"""

from .model_selector import ModelSelectorWidget
from .task_card import TaskCard, MergeOverlapsCard, CutpointCard, AssembleCard
from .task_popup_window import TaskPopupWindow, CollapsibleSection

# Chat sidebar backup (preserved for future use)
# from .chat_sidebar_backup import ChatSidebarPanel

__all__ = [
    'ModelSelectorWidget',
    'TaskCard',
    'MergeOverlapsCard',
    'CutpointCard',
    'AssembleCard',
    'TaskPopupWindow',
    'CollapsibleSection',
]
