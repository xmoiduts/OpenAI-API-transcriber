"""
Starred Models Storage - Manages persistence of starred models and providers.
Storage location: <project_root>/model_selector_starred.yaml
"""

import os
import yaml
from typing import Dict, List, Set
from pathlib import Path


class StarredStorage:
    """Manages starred models and providers persistence."""
    
    STORAGE_FILENAME = "model_selector_starred.yaml"
    
    def __init__(self):
        self._storage_path = self._get_storage_path()
        self._starred_models: Set[str] = set()
        self._starred_providers: Dict[str, str] = {}  # model_key -> provider_name (single)
        self._load()
    
    def _get_storage_path(self) -> Path:
        """Get storage file path in project root."""
        # Find project root by looking for config.yaml or going up from current file
        current = Path(__file__).resolve()
        
        # Traverse up to find project root (where config.yaml exists)
        for parent in current.parents:
            if (parent / "config.yaml").exists() or (parent / "config.example.yaml").exists():
                return parent / self.STORAGE_FILENAME
        
        # Fallback to current working directory
        return Path.cwd() / self.STORAGE_FILENAME
    
    def _load(self):
        """Load starred state from file."""
        if not self._storage_path.exists():
            return
        
        try:
            with open(self._storage_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            starred = data.get('starred', {})
            self._starred_models = set(starred.get('models', []))
            
            # Convert providers format: {model: [provider]} -> {model: provider}
            providers_data = starred.get('providers', {})
            for model, providers in providers_data.items():
                if providers:
                    # Only keep the first (should be single) starred provider
                    self._starred_providers[model] = providers[0] if isinstance(providers, list) else providers
                    
        except Exception as e:
            print(f"[StarredStorage] Error loading starred state: {e}")
    
    def _save(self):
        """Save starred state to file."""
        # Convert back to storage format
        providers_data = {}
        for model, provider in self._starred_providers.items():
            providers_data[model] = [provider]
        
        data = {
            'version': 1,
            'starred': {
                'models': list(self._starred_models),
                'providers': providers_data
            }
        }
        
        try:
            with open(self._storage_path, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
        except Exception as e:
            print(f"[StarredStorage] Error saving starred state: {e}")
    
    # Model starring
    def is_model_starred(self, model_key: str) -> bool:
        """Check if a model is starred."""
        return model_key in self._starred_models
    
    def toggle_model_star(self, model_key: str) -> bool:
        """Toggle star status for a model. Returns new status."""
        if model_key in self._starred_models:
            self._starred_models.discard(model_key)
            new_status = False
        else:
            self._starred_models.add(model_key)
            new_status = True
        self._save()
        return new_status
    
    def get_starred_models(self) -> List[str]:
        """Get list of starred model keys."""
        return list(self._starred_models)
    
    # Provider starring (single per model)
    def get_starred_provider(self, model_key: str) -> str | None:
        """Get starred provider for a model. Returns None if no starred provider."""
        return self._starred_providers.get(model_key)
    
    def set_starred_provider(self, model_key: str, provider_name: str | None):
        """Set or clear starred provider for a model. Only one provider can be starred per model."""
        if provider_name is None:
            self._starred_providers.pop(model_key, None)
        else:
            self._starred_providers[model_key] = provider_name
        self._save()
    
    def toggle_provider_star(self, model_key: str, provider_name: str) -> bool:
        """Toggle star for a provider. Unsets other starred providers for this model.
        Returns new status for this provider."""
        current = self._starred_providers.get(model_key)
        
        if current == provider_name:
            # Already starred, remove it
            self._starred_providers.pop(model_key, None)
            new_status = False
        else:
            # Set new starred provider (replaces any previous)
            self._starred_providers[model_key] = provider_name
            new_status = True
        
        self._save()
        return new_status
    
    def is_provider_starred(self, model_key: str, provider_name: str) -> bool:
        """Check if a specific provider is starred for a model."""
        return self._starred_providers.get(model_key) == provider_name


# Global singleton instance
_storage_instance: StarredStorage | None = None


def get_starred_storage() -> StarredStorage:
    """Get the global StarredStorage instance."""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StarredStorage()
    return _storage_instance

