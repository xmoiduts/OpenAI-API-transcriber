"""
Chatbot Core - Multi-vendor LLM chat interface.

Supports: OpenAI (gpt), Claude (Anthropic), Gemini (Google)
Decoupled from GUI, maintains internal chat history.
"""

from .data_types import ChatMessage, ChatThread, MessageRole
from .chat_core import ChatCore
from .model_resolver import ModelResolver, ResolvedModelConfig

__all__ = [
    'ChatMessage',
    'ChatThread', 
    'MessageRole',
    'ChatCore',
    'ModelResolver',
    'ResolvedModelConfig',
]
