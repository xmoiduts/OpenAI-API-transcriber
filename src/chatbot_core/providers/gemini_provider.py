"""
Google Gemini chat provider.

Uses the google-genai SDK as demonstrated in the reference project (anime-pv-ocr).
Supports streaming responses and custom base URLs for proxy endpoints.
"""

from typing import Optional, Generator, Callable, Dict, Any

from .base import ChatProvider, ChatResponse
from ..data_types import ChatThread
from ..model_resolver import ResolvedModelConfig
from ..thinking_resolver import resolve_thinking


class GeminiProvider(ChatProvider):
    """
    Provider for Google Gemini API.
    
    Based on the implementation in ../anime-pv-ocr/src/gemini_client.py.
    Uses google.genai SDK with streaming support.
    """
    
    def __init__(self, config: ResolvedModelConfig):
        super().__init__(config)
        self._client = None
    
    def _get_client(self):
        """Lazy initialize the Gemini client."""
        if self._client is None:
            try:
                import google.genai as genai
            except ImportError:
                raise ImportError(
                    "google-genai package is required for Gemini provider. "
                    "Install with: pip install google-genai"
                )
            
            client_kwargs = {
                "api_key": self.config.token,
            }
            
            # Custom base URL for proxy endpoints
            if self.config.endpoint:
                base_url = self.config.endpoint.rstrip('/')
                client_kwargs["http_options"] = {"base_url": base_url}
                print(f"[GeminiProvider] Using custom base URL: {base_url}")
            else:
                print("[GeminiProvider] Using default Google Gemini API endpoint")
            
            self._client = genai.Client(**client_kwargs)
        
        return self._client
    
    def chat(self, thread: ChatThread,
             temperature: Optional[float] = None,
             max_tokens: Optional[int] = None,
             request_options: Optional[Dict[str, Any]] = None) -> ChatResponse:
        """
        Send a chat request and return the complete response.
        """
        client = self._get_client()
        
        # Convert thread to Gemini format
        system_instruction, contents = thread.to_gemini_contents()
        
        # Build config
        config = self._build_config(temperature, max_tokens, system_instruction, request_options=request_options)
        
        try:
            response = client.models.generate_content(
                model=self.config.api_name,
                contents=self._format_contents(contents),
                config=config,
            )
            
            # Extract content
            content = ""
            if response.candidates:
                for cand in response.candidates:
                    if cand.content and cand.content.parts:
                        for part in cand.content.parts:
                            if hasattr(part, 'text') and part.text:
                                content += part.text
            
            # Usage
            usage = {}
            if response.usage_metadata:
                usage = {
                    "prompt_tokens": response.usage_metadata.prompt_token_count or 0,
                    "completion_tokens": response.usage_metadata.candidates_token_count or 0,
                    "total_tokens": (response.usage_metadata.prompt_token_count or 0) + 
                                   (response.usage_metadata.candidates_token_count or 0),
                }
            
            finish_reason = None
            if response.candidates and response.candidates[0].finish_reason:
                finish_reason = str(response.candidates[0].finish_reason)
            
            return ChatResponse(
                content=content,
                model=self.config.model_key,
                provider=self.config.provider,
                finish_reason=finish_reason,
                usage=usage,
                raw_response=response,
            )
            
        except Exception as e:
            print(f"[GeminiProvider] Error: {e}")
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
        
        # Convert thread to Gemini format
        system_instruction, contents = thread.to_gemini_contents()
        
        # Build config
        config = self._build_config(temperature, max_tokens, system_instruction, request_options=request_options)
        
        full_content = ""
        usage = {}
        finish_reason = None
        
        try:
            for chunk in client.models.generate_content_stream(
                model=self.config.api_name,
                contents=self._format_contents(contents),
                config=config,
            ):
                # Update usage metadata
                if chunk.usage_metadata:
                    usage = {
                        "prompt_tokens": chunk.usage_metadata.prompt_token_count or 0,
                        "completion_tokens": chunk.usage_metadata.candidates_token_count or 0,
                        "total_tokens": (chunk.usage_metadata.prompt_token_count or 0) +
                                       (chunk.usage_metadata.candidates_token_count or 0),
                    }
                
                # Extract text from chunk
                if chunk.candidates:
                    for cand in chunk.candidates:
                        if cand.content and cand.content.parts:
                            for part in cand.content.parts:
                                if hasattr(part, 'text') and part.text:
                                    full_content += part.text
                                    if on_token:
                                        on_token(part.text)
                                    yield part.text
                        
                        if cand.finish_reason:
                            finish_reason = str(cand.finish_reason)
            
            return ChatResponse(
                content=full_content,
                model=self.config.model_key,
                provider=self.config.provider,
                finish_reason=finish_reason,
                usage=usage,
                raw_response=None,
            )
            
        except Exception as e:
            print(f"[GeminiProvider] Stream error: {e}")
            raise
    
    def _build_config(
        self,
        temperature: Optional[float],
        max_tokens: Optional[int],
        system_instruction: Optional[str],
        *,
        request_options: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """Build generation config for Gemini API."""
        try:
            import google.genai.types as types
        except ImportError:
            types = None
        
        config = {}
        
        # Temperature
        temp = self._resolve_temperature(temperature)
        if temp is not None:
            config["temperature"] = temp
        
        # Top P
        if self.config.default_top_p is not None:
            config["top_p"] = self.config.default_top_p
        
        # Max tokens
        max_tok = self._resolve_max_tokens(max_tokens)
        if max_tok:
            config["max_output_tokens"] = max_tok
        
        # System instruction
        if system_instruction:
            config["system_instruction"] = system_instruction

        # Thinking config (Gemini 2.5 budget / Gemini 3 level)
        try:
            thinking_level = (request_options or {}).get("thinking_level")
            task_key = (request_options or {}).get("task_key")
            resolved = resolve_thinking(self.config, thinking_level, task_key=task_key)
            if resolved.gemini_thinking_config:
                if types is not None:
                    try:
                        # google.genai.types.ThinkingConfig uses snake_case fields
                        config["thinking_config"] = types.ThinkingConfig(**resolved.gemini_thinking_config)
                    except Exception:
                        config["thinking_config"] = resolved.gemini_thinking_config
                else:
                    config["thinking_config"] = resolved.gemini_thinking_config
        except Exception as e:
            print(f"[GeminiProvider] Warning: thinking resolver failed: {e}")
        
        return config if config else None
    
    def _format_contents(self, contents: list) -> list:
        """
        Format contents for Gemini API.
        
        Converts our internal format to what Gemini expects.
        """
        formatted = []
        
        for c in contents:
            role = c.get('role', 'user')
            parts = c.get('parts', [])
            
            # Extract text parts
            text_parts = []
            for part in parts:
                if isinstance(part, dict) and 'text' in part:
                    text_parts.append(part['text'])
                elif isinstance(part, str):
                    text_parts.append(part)
            
            if text_parts:
                # For simple text content, just use the text directly
                formatted.append({
                    "role": role,
                    "parts": [{"text": '\n'.join(text_parts)}]
                })
        
        return formatted
