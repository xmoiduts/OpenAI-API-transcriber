"""
OpenAI-compatible chat provider.

Handles both official OpenAI API and OpenAI-compatible endpoints (aihubmix, etc.)
Uses the openai Python package.
"""

from typing import Optional, Generator, Callable, Dict, Any

from .base import ChatProvider, ChatResponse
from ..data_types import ChatThread
from ..model_resolver import ResolvedModelConfig
from ..thinking_resolver import resolve_thinking


class OpenAIProvider(ChatProvider):
    """
    Provider for OpenAI and OpenAI-compatible APIs.
    
    Supports the OpenAI chat completions API format.
    """
    
    def __init__(self, config: ResolvedModelConfig):
        super().__init__(config)
        self._client = None
    
    def _get_client(self):
        """Lazy initialize the OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError:
                raise ImportError(
                    "openai package is required for OpenAI provider. "
                    "Install with: pip install openai"
                )
            
            # Build base URL from endpoint
            base_url = self.config.endpoint
            if base_url and not base_url.endswith('/v1'):
                base_url = base_url.rstrip('/') + '/v1'
            
            self._client = OpenAI(
                api_key=self.config.token,
                base_url=base_url,
            )
        return self._client
    
    def chat(self, thread: ChatThread,
             temperature: Optional[float] = None,
             max_tokens: Optional[int] = None,
             request_options: Optional[Dict[str, Any]] = None) -> ChatResponse:
        """
        Send a chat request and return the complete response.
        """
        client = self._get_client()
        
        # Convert thread to OpenAI format
        messages = thread.to_openai_messages()
        
        # Build request parameters
        params = {
            "model": self.config.api_name,
            "messages": messages,
        }

        # Thinking / reasoning (best-effort; may be ignored by endpoint)
        try:
            thinking_level = (request_options or {}).get("thinking_level")
            task_key = (request_options or {}).get("task_key")
            resolved = resolve_thinking(self.config, thinking_level, task_key=task_key)
            if resolved.openai_params:
                params.update(resolved.openai_params)
            if resolved.openai_extra_body:
                # OpenAI SDK supports this kwarg for vendor extensions (e.g., Qwen enable_thinking)
                params["extra_body"] = resolved.openai_extra_body
        except Exception as e:
            print(f"[OpenAIProvider] Warning: thinking resolver failed: {e}")
        
        # Temperature
        temp = self._resolve_temperature(temperature)
        if temp is not None:
            params["temperature"] = temp
        
        # Top P (only if temperature not set, for some models)
        if temp is None and self.config.default_top_p is not None:
            params["top_p"] = self.config.default_top_p
        
        # Max tokens
        max_tok = self._resolve_max_tokens(max_tokens)
        if max_tok and self._should_include_max_tokens(max_tok):
            params["max_tokens"] = max_tok
        
        try:
            response = client.chat.completions.create(**params)
            
            content = response.choices[0].message.content or ""
            finish_reason = response.choices[0].finish_reason
            
            usage = {}
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            
            return ChatResponse(
                content=content,
                model=self.config.model_key,
                provider=self.config.provider,
                finish_reason=finish_reason,
                usage=usage,
                raw_response=response,
            )
            
        except Exception as e:
            print(f"[OpenAIProvider] Error: {e}")
            raise
    
    def chat_stream(self, thread: ChatThread,
                    temperature: Optional[float] = None,
                    max_tokens: Optional[int] = None,
                    request_options: Optional[Dict[str, Any]] = None,
                    on_token: Optional[Callable[[str], None]] = None) -> Generator[str, None, ChatResponse]:
        """
        Send a chat request and stream the response.
        """
        client = self._get_client()
        
        # Convert thread to OpenAI format
        messages = thread.to_openai_messages()
        
        # Build request parameters
        params = {
            "model": self.config.api_name,
            "messages": messages,
            "stream": True,
        }

        # Thinking / reasoning (best-effort; may be ignored by endpoint)
        try:
            thinking_level = (request_options or {}).get("thinking_level")
            task_key = (request_options or {}).get("task_key")
            resolved = resolve_thinking(self.config, thinking_level, task_key=task_key)
            if resolved.openai_params:
                params.update(resolved.openai_params)
            if resolved.openai_extra_body:
                params["extra_body"] = resolved.openai_extra_body
        except Exception as e:
            print(f"[OpenAIProvider] Warning: thinking resolver failed: {e}")
        
        # Temperature
        temp = self._resolve_temperature(temperature)
        if temp is not None:
            params["temperature"] = temp
        
        # Top P
        if temp is None and self.config.default_top_p is not None:
            params["top_p"] = self.config.default_top_p
        
        # Max tokens
        max_tok = self._resolve_max_tokens(max_tokens)
        if max_tok and self._should_include_max_tokens(max_tok):
            params["max_tokens"] = max_tok
        
        full_content = ""
        finish_reason = None
        
        try:
            stream = client.chat.completions.create(**params)
            
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        full_content += delta.content
                        if on_token:
                            on_token(delta.content)
                        yield delta.content
                    
                    if chunk.choices[0].finish_reason:
                        finish_reason = chunk.choices[0].finish_reason
            
            return ChatResponse(
                content=full_content,
                model=self.config.model_key,
                provider=self.config.provider,
                finish_reason=finish_reason,
                usage={},  # Stream doesn't provide usage
                raw_response=None,
            )
            
        except Exception as e:
            print(f"[OpenAIProvider] Stream error: {e}")
            raise
