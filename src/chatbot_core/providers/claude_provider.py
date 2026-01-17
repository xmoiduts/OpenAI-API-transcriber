"""
Claude/Anthropic chat provider.

Uses the anthropic Python package for direct Anthropic API access.
Also supports OpenAI-compatible endpoints for Claude via proxy services.
"""

from typing import Optional, Generator, Callable

from .base import ChatProvider, ChatResponse
from ..data_types import ChatThread
from ..model_resolver import ResolvedModelConfig


class ClaudeProvider(ChatProvider):
    """
    Provider for Claude via Anthropic API.
    
    Note: When using proxy services (aihubmix, etc.) that expose Claude via
    OpenAI-compatible API, use OpenAIProvider instead. This provider is for
    direct Anthropic API access.
    """
    
    def __init__(self, config: ResolvedModelConfig):
        super().__init__(config)
        self._client = None
    
    def _get_client(self):
        """Lazy initialize the Anthropic client."""
        if self._client is None:
            try:
                from anthropic import Anthropic
            except ImportError:
                raise ImportError(
                    "anthropic package is required for Claude provider. "
                    "Install with: pip install anthropic"
                )
            
            # Build client kwargs
            client_kwargs = {
                "api_key": self.config.token,
            }
            
            # Custom base URL if provided
            if self.config.endpoint:
                # Anthropic client expects base_url without /v1
                base_url = self.config.endpoint.rstrip('/')
                if base_url.endswith('/v1'):
                    base_url = base_url[:-3]
                client_kwargs["base_url"] = base_url
            
            self._client = Anthropic(**client_kwargs)
        
        return self._client
    
    def chat(self, thread: ChatThread,
             temperature: Optional[float] = None,
             max_tokens: Optional[int] = None) -> ChatResponse:
        """
        Send a chat request and return the complete response.
        """
        client = self._get_client()
        
        # Convert thread to Claude format
        system_prompt, messages = thread.to_claude_messages()
        
        # Build request parameters
        params = {
            "model": self.config.api_name,
            "messages": messages,
        }
        
        # System prompt
        if system_prompt:
            params["system"] = system_prompt
        
        # Temperature
        temp = self._resolve_temperature(temperature)
        if temp is not None:
            params["temperature"] = temp
        
        # Top P (only if temperature not explicitly set)
        if temp is None and self.config.default_top_p is not None:
            params["top_p"] = self.config.default_top_p
        
        # Max tokens (required for Claude)
        max_tok = self._resolve_max_tokens(max_tokens)
        if max_tok:
            params["max_tokens"] = max_tok
        else:
            # Claude requires max_tokens, use a sensible default
            params["max_tokens"] = 4096
        
        try:
            response = client.messages.create(**params)
            
            # Extract content from response
            content = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    content += block.text
            
            usage = {}
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                }
            
            return ChatResponse(
                content=content,
                model=self.config.model_key,
                provider=self.config.provider,
                finish_reason=response.stop_reason,
                usage=usage,
                raw_response=response,
            )
            
        except Exception as e:
            print(f"[ClaudeProvider] Error: {e}")
            raise
    
    def chat_stream(self, thread: ChatThread,
                    temperature: Optional[float] = None,
                    max_tokens: Optional[int] = None,
                    on_token: Optional[Callable[[str], None]] = None) -> Generator[str, None, ChatResponse]:
        """
        Send a chat request and stream the response.
        """
        client = self._get_client()
        
        # Convert thread to Claude format
        system_prompt, messages = thread.to_claude_messages()
        
        # Build request parameters
        params = {
            "model": self.config.api_name,
            "messages": messages,
        }
        
        # System prompt
        if system_prompt:
            params["system"] = system_prompt
        
        # Temperature
        temp = self._resolve_temperature(temperature)
        if temp is not None:
            params["temperature"] = temp
        
        # Top P
        if temp is None and self.config.default_top_p is not None:
            params["top_p"] = self.config.default_top_p
        
        # Max tokens (required for Claude)
        max_tok = self._resolve_max_tokens(max_tokens)
        if max_tok:
            params["max_tokens"] = max_tok
        else:
            params["max_tokens"] = 4096
        
        full_content = ""
        finish_reason = None
        usage = {}
        
        try:
            with client.messages.stream(**params) as stream:
                for text in stream.text_stream:
                    full_content += text
                    if on_token:
                        on_token(text)
                    yield text
                
                # Get final message for metadata
                final_message = stream.get_final_message()
                if final_message:
                    finish_reason = final_message.stop_reason
                    if final_message.usage:
                        usage = {
                            "prompt_tokens": final_message.usage.input_tokens,
                            "completion_tokens": final_message.usage.output_tokens,
                            "total_tokens": final_message.usage.input_tokens + final_message.usage.output_tokens,
                        }
            
            return ChatResponse(
                content=full_content,
                model=self.config.model_key,
                provider=self.config.provider,
                finish_reason=finish_reason,
                usage=usage,
                raw_response=None,
            )
            
        except Exception as e:
            print(f"[ClaudeProvider] Stream error: {e}")
            raise
