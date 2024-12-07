import yaml
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from functools import lru_cache

class ConfigManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._config_path = Path("config.yaml")
        self._config = self._load_config()
        self._initialized = True
        self._log_callback = None  # Initialize log callback as None
    
    def set_log_callback(self, callback: Optional[Callable[[str], None]]):
        """Set the logging callback function"""
        self._log_callback = callback
    
    def _log(self, message: str):
        """Internal logging method"""
        if self._log_callback:
            self._log_callback(message)
        else:
            print(message)  # Fallback to print if no callback set
    
    def _load_config(self) -> dict:
        """Load configuration from yaml file"""
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            self._log(f"Error loading config: {e}")
            return {}
    
    def get_proxy_for_provider(self, model: str, provider: str) -> Optional[Dict[str, str]]:
        """Get proxy settings for a specific provider"""
        try:
            # Check if provider needs proxy
            proxy_name = self._config.get('api', {}).get('providers', {})\
                .get(provider, {}).get('recommend-proxy', {})
            self._log(f"Recommended proxy name for {provider}: {proxy_name}")
            
            if not proxy_name:
                return None
            
            # Get proxy configuration
            proxy_config = self._config.get('proxies', {}).get(proxy_name, {})
            self._log(f"Proxy configuration for {proxy_name}: {proxy_config}")
            
            if not proxy_config:
                return None
            
            host = proxy_config.get('host')
            port = proxy_config.get('port')
            if not host or not port:
                return None
            
            proxy_urls = {
                'http': f'http://{host}:{port}',
                'https': f'http://{host}:{port}'
            }
            self._log(f"Using proxy settings: {proxy_urls}")
            return proxy_urls
            
        except Exception as e:
            self._log(f"Error getting proxy settings: {e}")
            return None
    
    def get_provider_endpoint(self, provider: str) -> Optional[str]:
        """Get API endpoint for a provider"""
        return self._config.get('api', {}).get('providers', {})\
            .get(provider, {}).get('endpoint')
    
    def get_provider_token(self, provider: str) -> Optional[str]:
        """Get API token for a provider"""
        return self._config.get('api', {}).get('providers', {})\
            .get(provider, {}).get('token')
    
    def get_model_config(self, model: str) -> Dict[str, Any]:
        """Get configuration for a specific model"""
        return self._config.get('api', {}).get('models', {})\
            .get(model, {})
    
    def get_paths_config(self) -> Dict[str, str]:
        """Get paths configuration"""
        return self._config.get('paths', {})