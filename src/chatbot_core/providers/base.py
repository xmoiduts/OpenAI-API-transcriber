"""
Base interface for chat providers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Generator, Dict, Any, Callable
import sys

sys.path.insert(0, str(__file__).rsplit('src', 1)[0])

from ..data_types import ChatThread, ChatMessage
from ..model_resolver import ResolvedModelConfig


@dataclass
class ChatResponse:
    """
    Response from a chat completion.
    
    Attributes:
        content: The generated text content
        model: Model that generated the response
        provider: Provider used
        finish_reason: Why generation stopped (e.g., "stop", "length")
        usage: Token usage statistics
        raw_response: Original vendor response object
    """
    content: str
    model: str
    provider: str
    finish_reason: Optional[str] = None
    usage: Dict[str, int] = field(default_factory=dict)
    raw_response: Any = None


class ChatProvider(ABC):
    """
    Abstract base class for chat providers.
    
    Each provider implementation handles the specifics of communicating
    with a particular vendor's API (OpenAI, Claude, Gemini, etc.)
    """
    
    def __init__(self, config: ResolvedModelConfig):
        """
        Initialize the provider with a resolved configuration.
        
        Args:
            config: Flattened model configuration from ModelResolver
        """
        self.config = config
    
    @abstractmethod
    def chat(self, thread: ChatThread, 
             temperature: Optional[float] = None,
             max_tokens: Optional[int] = None) -> ChatResponse:
        """
        Send a chat request and return the complete response.
        
        Args:
            thread: The conversation thread
            temperature: Override temperature (uses config default if None)
            max_tokens: Override max tokens
            
        Returns:
            ChatResponse with the generated content
        """
        pass
    
    @abstractmethod
    def chat_stream(self, thread: ChatThread,
                    temperature: Optional[float] = None,
                    max_tokens: Optional[int] = None,
                    on_token: Optional[Callable[[str], None]] = None) -> Generator[str, None, ChatResponse]:
        """
        Send a chat request and stream the response.
        
        Args:
            thread: The conversation thread
            temperature: Override temperature
            max_tokens: Override max tokens
            on_token: Optional callback for each token
            
        Yields:
            Text chunks as they arrive
            
        Returns:
            Final ChatResponse after completion
        """
        pass
    
    def _resolve_temperature(self, temperature: Optional[float]) -> Optional[float]:
        """Resolve temperature parameter."""
        if temperature is not None:
            return temperature
        return self.config.default_temperature
    
    def _resolve_max_tokens(self, max_tokens: Optional[int]) -> Optional[int]:
        """Resolve max_tokens parameter."""
        if max_tokens is not None:
            return max_tokens
        return self.config.max_output_tokens
    
    def _should_include_max_tokens(self, max_tokens: Optional[int]) -> bool:
        """
        Check if max_tokens should be included in request.
        
        Some models (Claude) require explicit max_tokens above a threshold.
        """
        threshold = self.config.include_max_tokens_above
        if threshold is None:
            return True
        return max_tokens is not None and max_tokens > threshold
