"""
Model Selector Widget - A reusable PyQt5 component for selecting AI models and providers.

Usage:
    from src.gui.components.model_selector import ModelSelectorWidget
    
    selector = ModelSelectorWidget(applicable_task="audio-transcription")
    selector.selection_confirmed.connect(on_model_selected)
"""

from .model_selector_widget import ModelSelectorWidget

__all__ = ["ModelSelectorWidget"]

