"""
ChatCore - Unified chat interface for multiple LLM providers.

Manages conversation thread and routes requests to appropriate providers
based on the selected model's api-scheme.
"""

from typing import Optional, Callable, Generator
from enum import Enum

from .data_types import ChatThread, ChatMessage, MessageRole
from .model_resolver import ModelResolver, ResolvedModelConfig
from .providers.base import ChatProvider, ChatResponse
from .providers.openai_provider import OpenAIProvider
from .providers.claude_provider import ClaudeProvider
from .providers.gemini_provider import GeminiProvider


class ApiScheme(Enum):
    """Known API schemes from config."""
    OPENAI_GPT = "openai-gpt"
    ANTHROPIC_CLAUDE = "anthropic-claude"
    GOOGLE_GEMINI = "google-gemini"
    OPENAI_WHISPER = "openai-whisper"  # Not for chat, but recognized


class ChatCore:
    """
    Main chat interface - manages thread and routes to providers.
    
    This class is GUI-agnostic and can be used from any interface.
    It maintains an internal chat thread and handles provider switching.
    
    Usage:
        core = ChatCore()
        core.set_model("gemini-2.5-flash", "aihubmix")
        core.set_system_prompt("You are a helpful assistant.")
        
        # Synchronous
        response = core.send("Hello!")
        
        # Streaming
        for chunk in core.send_stream("Hello!"):
            print(chunk, end="", flush=True)
    """
    
    def __init__(self, system_prompt: Optional[str] = None):
        """
        Initialize ChatCore.
        
        Args:
            system_prompt: Optional initial system prompt
        """
        self._resolver = ModelResolver()
        self._thread = ChatThread()
        self._current_config: Optional[ResolvedModelConfig] = None
        self._current_provider: Optional[ChatProvider] = None
        
        # Callbacks
        self._on_response_start: Optional[Callable[[], None]] = None
        self._on_response_chunk: Optional[Callable[[str], None]] = None
        self._on_response_complete: Optional[Callable[[ChatResponse], None]] = None
        self._on_error: Optional[Callable[[Exception], None]] = None
        
        if system_prompt:
            self.set_system_prompt(system_prompt)
    
    # ─────────────────────────────────────────────────────────────────────
    # Configuration
    # ─────────────────────────────────────────────────────────────────────
    
    def set_model(self, model_key: str, provider: str, 
                  variant: Optional[str] = None) -> bool:
        """
        Set the current model and provider.
        
        Args:
            model_key: Model key from config (e.g., "gemini-2.5-flash")
            provider: Provider name (e.g., "aihubmix")
            variant: Optional variant name
            
        Returns:
            True if successful, False if model/provider not found
        """
        config = self._resolver.resolve(model_key, provider, variant)
        if config is None:
            print(f"[ChatCore] Failed to resolve model: {model_key} @ {provider}")
            return False
        
        self._current_config = config
        self._current_provider = self._create_provider(config)
        
        if self._current_provider is None:
            print(f"[ChatCore] Unsupported api-scheme: {config.api_scheme}")
            return False
        
        print(f"[ChatCore] Model set: {config.display_name} @ {provider} (scheme: {config.api_scheme})")
        return True
    
    def _create_provider(self, config: ResolvedModelConfig) -> Optional[ChatProvider]:
        """Create appropriate provider based on api-scheme.
        
        Routes to native provider implementations based on the configured api-scheme.
        Proxy services (aihubmix, openrouter, etc.) support native API formats.
        """
        scheme = config.api_scheme
        
        if scheme == ApiScheme.OPENAI_GPT.value:
            return OpenAIProvider(config)
        elif scheme == ApiScheme.ANTHROPIC_CLAUDE.value:
            return ClaudeProvider(config)
        elif scheme == ApiScheme.GOOGLE_GEMINI.value:
            return GeminiProvider(config)
        else:
            # For unknown schemes, try OpenAI-compatible as fallback
            print(f"[ChatCore] Unknown scheme '{scheme}', trying OpenAI-compatible")
            return OpenAIProvider(config)
    
    def set_system_prompt(self, prompt: str) -> None:
        """
        Set or update the system prompt.
        
        If a system message already exists, it will be replaced.
        """
        # Remove existing system message
        self._thread.messages = [
            m for m in self._thread.messages 
            if m.role != MessageRole.SYSTEM
        ]
        
        # Add new system message at the beginning
        system_msg = ChatMessage.system(prompt)
        self._thread.messages.insert(0, system_msg)
    
    def get_system_prompt(self) -> Optional[str]:
        """Get current system prompt."""
        msg = self._thread.get_system_message()
        return msg.content if msg else None
    
    # ─────────────────────────────────────────────────────────────────────
    # Callbacks
    # ─────────────────────────────────────────────────────────────────────
    
    def set_callbacks(
        self,
        on_response_start: Optional[Callable[[], None]] = None,
        on_response_chunk: Optional[Callable[[str], None]] = None,
        on_response_complete: Optional[Callable[[ChatResponse], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Set callbacks for response handling."""
        self._on_response_start = on_response_start
        self._on_response_chunk = on_response_chunk
        self._on_response_complete = on_response_complete
        self._on_error = on_error
    
    # ─────────────────────────────────────────────────────────────────────
    # Chat Operations
    # ─────────────────────────────────────────────────────────────────────
    
    def send(self, message: str, 
             temperature: Optional[float] = None,
             max_tokens: Optional[int] = None,
             thinking_level: Optional[str] = None,
             task_key: Optional[str] = None) -> Optional[str]:
        """
        Send a message and get the complete response.
        
        Args:
            message: User message to send
            temperature: Override temperature
            max_tokens: Override max tokens
            
        Returns:
            Assistant response text, or None on error
        """
        if not self._current_provider:
            print("[ChatCore] No model selected. Call set_model() first.")
            return None
        
        # Add user message to thread
        self._thread.add_user(message)
        
        try:
            if self._on_response_start:
                self._on_response_start()
            
            response = self._current_provider.chat(
                self._thread,
                temperature=temperature,
                max_tokens=max_tokens,
                request_options={
                    "thinking_level": thinking_level,
                    "task_key": task_key,
                },
            )
            
            # Add assistant response to thread
            self._thread.add_assistant(
                response.content,
                model=response.model,
                provider=response.provider,
            )
            
            if self._on_response_complete:
                self._on_response_complete(response)
            
            return response.content
            
        except Exception as e:
            if self._on_error:
                self._on_error(e)
            else:
                print(f"[ChatCore] Error: {e}")
            return None
    
    def send_stream(self, message: str,
                    temperature: Optional[float] = None,
                    max_tokens: Optional[int] = None,
                    thinking_level: Optional[str] = None,
                    task_key: Optional[str] = None) -> Generator[str, None, Optional[str]]:
        """
        Send a message and stream the response.
        
        Args:
            message: User message to send
            temperature: Override temperature
            max_tokens: Override max tokens
            
        Yields:
            Text chunks as they arrive
            
        Returns:
            Complete response text, or None on error
        """
        if not self._current_provider:
            print("[ChatCore] No model selected. Call set_model() first.")
            return None
        
        # Add user message to thread
        self._thread.add_user(message)
        
        try:
            if self._on_response_start:
                self._on_response_start()
            
            full_content = ""
            
            gen = self._current_provider.chat_stream(
                self._thread,
                temperature=temperature,
                max_tokens=max_tokens,
                request_options={
                    "thinking_level": thinking_level,
                    "task_key": task_key,
                },
                on_token=self._on_response_chunk,
            )
            
            # Iterate through the generator
            response = None
            try:
                while True:
                    chunk = next(gen)
                    full_content += chunk
                    yield chunk
            except StopIteration as e:
                response = e.value
            
            # Add assistant response to thread
            if response:
                self._thread.add_assistant(
                    response.content,
                    model=response.model,
                    provider=response.provider,
                )
                
                if self._on_response_complete:
                    self._on_response_complete(response)
                
                return response.content
            else:
                # Fallback if generator didn't return properly
                self._thread.add_assistant(
                    full_content,
                    model=self._current_config.model_key if self._current_config else None,
                    provider=self._current_config.provider if self._current_config else None,
                )
                return full_content
            
        except Exception as e:
            if self._on_error:
                self._on_error(e)
            else:
                print(f"[ChatCore] Stream error: {e}")
            return None
    
    # ─────────────────────────────────────────────────────────────────────
    # Thread Management
    # ─────────────────────────────────────────────────────────────────────
    
    def clear_history(self) -> None:
        """Clear chat history (keeps system prompt)."""
        self._thread.clear()
    
    def get_thread(self) -> ChatThread:
        """Get the current chat thread."""
        return self._thread
    
    def get_messages(self) -> list:
        """Get all messages in the thread."""
        return self._thread.messages
    
    def get_conversation_messages(self) -> list:
        """Get conversation messages (excludes system prompt)."""
        return self._thread.get_conversation_messages()
    
    # ─────────────────────────────────────────────────────────────────────
    # Model Info
    # ─────────────────────────────────────────────────────────────────────
    
    def get_current_model(self) -> Optional[str]:
        """Get current model key."""
        return self._current_config.model_key if self._current_config else None
    
    def get_current_provider(self) -> Optional[str]:
        """Get current provider name."""
        return self._current_config.provider if self._current_config else None
    
    def get_current_config(self) -> Optional[ResolvedModelConfig]:
        """Get current resolved configuration."""
        return self._current_config
    
    def get_available_models(self, task: str = "text-chat") -> list:
        """Get list of models available for a task."""
        return self._resolver.get_models_for_task(task)
    
    def reload_config(self) -> None:
        """Reload configuration from file."""
        self._resolver.reload()
        
        # Re-resolve current model if set
        if self._current_config:
            self.set_model(
                self._current_config.model_key,
                self._current_config.provider,
            )
