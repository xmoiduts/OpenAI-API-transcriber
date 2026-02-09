"""
Model configuration resolver - flattens config.yaml model definitions.

Handles the nested structure of models -> variants -> providers and produces
a flat, ready-to-use configuration for API calls.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from pathlib import Path
import yaml


@dataclass
class ResolvedModelConfig:
    """
    Flattened model configuration ready for API use.
    
    This structure contains all parameters needed to make an API call,
    resolved from the nested config.yaml structure.
    """
    # Identity
    model_key: str           # Key in config (e.g., "gemini-2.5-flash")
    display_name: str        # Human-readable name
    model_family: str        # e.g., "Gemini", "Claude"
    
    # API routing
    api_scheme: str          # "openai-gpt", "anthropic-claude", "google-gemini"
    api_name: str            # Actual model name to send to API
    provider: str            # Provider key (e.g., "aihubmix")
    endpoint: str            # API endpoint URL
    token: str               # API token/key
    
    # Parameters
    max_input_tokens: Optional[int] = None
    max_output_tokens: Optional[int] = None
    include_max_tokens_above: Optional[int] = None  # Send max_tokens if output > this
    default_temperature: Optional[float] = None
    default_top_p: Optional[float] = None
    
    # Proxy (if needed)
    proxy: Optional[Dict[str, str]] = None  # {"http": "...", "https": "..."}
    
    # Raw config for provider-specific needs
    raw_model_config: Dict[str, Any] = None
    raw_provider_config: Dict[str, Any] = None


class ModelResolver:
    """
    Resolves model configurations from config.yaml.
    
    Handles the flattening of nested model -> variant -> provider structures
    and provides ready-to-use ResolvedModelConfig objects.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the resolver.
        
        Args:
            config_path: Path to config.yaml. If None, searches parent directories.
        """
        self._config_path = config_path or self._find_config()
        self._config = self._load_config()
    
    def _find_config(self) -> Path:
        """Find config.yaml by searching parent directories."""
        current = Path(__file__).resolve()
        
        for parent in current.parents:
            config_path = parent / "config.yaml"
            if config_path.exists():
                return config_path
        
        # Fallback to current directory
        return Path("config.yaml")
    
    def _load_config(self) -> Dict:
        """Load configuration from yaml file."""
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"[ModelResolver] Error loading config: {e}")
            return {}
    
    def reload(self) -> None:
        """Reload configuration from file."""
        self._config = self._load_config()
    
    def get_models_for_task(self, task: str) -> List[str]:
        """
        Get list of model keys that support a given task.
        
        Args:
            task: Task name (e.g., "text-chat", "audio-transcription")
            
        Returns:
            List of model keys
        """
        models = []
        models_config = self._config.get('api', {}).get('models', {})
        
        for model_key, model_data in models_config.items():
            applicable_tasks = model_data.get('applicable-tasks', [])
            if task in applicable_tasks:
                models.append(model_key)
        
        return models
    
    def resolve(self, model_key: str, provider: str, 
                variant: Optional[str] = None) -> Optional[ResolvedModelConfig]:
        """
        Resolve a model configuration to flat, usable form.
        
        Args:
            model_key: The model key from config (e.g., "gemini-2.5-flash")
            provider: The provider to use (e.g., "aihubmix")
            variant: Optional variant name (e.g., "dated-20250514")
            
        Returns:
            ResolvedModelConfig or None if not found
        """
        models_config = self._config.get('api', {}).get('models', {})
        providers_config = self._config.get('api', {}).get('providers', {})
        proxies_config = self._config.get('proxies', {})
        
        if model_key not in models_config:
            print(f"[ModelResolver] Model not found: {model_key}")
            return None
        
        model_data = models_config[model_key]
        
        # Get provider endpoint and token from global providers config
        if provider not in providers_config:
            print(f"[ModelResolver] Provider not found: {provider}")
            return None
        
        provider_global = providers_config[provider]
        if not isinstance(provider_global, dict):
            provider_global = {}
        
        endpoint = provider_global.get('endpoint', '')
        token = provider_global.get('token', '')
        
        # Resolve provider-specific model config
        # Priority: variant.providers.{provider} > model.providers.{provider}
        provider_model_config = {}
        
        if variant:
            # Check variant-specific provider config
            variants = model_data.get('variants', {})
            if variant in variants:
                variant_data = variants[variant]
                variant_providers = variant_data.get('providers', {})
                if provider in variant_providers:
                    provider_model_config = variant_providers[provider] or {}
        
        # Fallback to model-level provider config
        if not provider_model_config:
            model_providers = model_data.get('providers', {})
            if provider in model_providers:
                provider_model_config = model_providers[provider] or {}
        
        # Handle None or non-dict provider_model_config
        if not isinstance(provider_model_config, dict):
            provider_model_config = {}
        
        # Allow per-model/provider endpoint override (useful when one provider
        # hosts multiple API schemes under different path prefixes, e.g.
        # Gemini at /gemini).
        endpoint_override = provider_model_config.get('endpoint')
        if endpoint_override:
            endpoint = endpoint_override

        # Resolve api-name: provider-specific > model key
        api_name = provider_model_config.get('api-name', model_key)
        
        # Resolve parameters with fallbacks
        params = model_data.get('parameters', {})
        
        # Handle "None" strings from YAML (written as `None` becomes string "None")
        def parse_param(value):
            if value is None or value == 'None' or value == 'none':
                return None
            return value
        
        # Handle proxy
        proxy = None
        recommend_proxy = provider_global.get('recommend-proxy')
        if recommend_proxy and recommend_proxy in proxies_config:
            proxy_config = proxies_config[recommend_proxy]
            host = proxy_config.get('host')
            port = proxy_config.get('port')
            if host and port:
                proxy = {
                    'http': f'http://{host}:{port}',
                    'https': f'http://{host}:{port}'
                }
        
        # Max tokens - can be overridden by variant/provider
        max_input = provider_model_config.get('max-input-tokens', 
                                               model_data.get('max-input-tokens'))
        max_output = provider_model_config.get('max-output-tokens',
                                                model_data.get('max-output-tokens'))
        
        return ResolvedModelConfig(
            model_key=model_key,
            display_name=model_data.get('display-name', model_key),
            model_family=model_data.get('model-family', 'Unknown'),
            api_scheme=model_data.get('api-scheme', 'unknown'),
            api_name=api_name,
            provider=provider,
            endpoint=endpoint,
            token=token,
            max_input_tokens=max_input,
            max_output_tokens=max_output,
            include_max_tokens_above=model_data.get('include-max_tokens-above'),
            default_temperature=parse_param(params.get('default-temperature')),
            default_top_p=parse_param(params.get('default-top-p')),
            proxy=proxy,
            raw_model_config=model_data,
            raw_provider_config=provider_model_config,
        )
    
    def get_provider_for_model(self, model_key: str) -> Optional[str]:
        """
        Get the first available provider for a model.
        
        Useful for getting a default provider when none is specified.
        """
        models_config = self._config.get('api', {}).get('models', {})
        
        if model_key not in models_config:
            return None
        
        model_data = models_config[model_key]
        providers = model_data.get('providers', {})
        
        if not isinstance(providers, dict) or not providers:
            return None
        
        return next(iter(providers.keys()))
    
    def get_api_scheme(self, model_key: str) -> Optional[str]:
        """Get the API scheme for a model."""
        models_config = self._config.get('api', {}).get('models', {})
        
        if model_key not in models_config:
            return None
        
        return models_config[model_key].get('api-scheme')
