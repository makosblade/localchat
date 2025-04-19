from typing import Dict, Type

from localchat.services.adapters.base_adapter import ModelProviderAdapter
from localchat.services.adapters.ollama_adapter import OllamaAdapter
from localchat.services.adapters.openai_adapter import OpenAIAdapter
from localchat.services.adapters.anthropic_adapter import AnthropicAdapter
from localchat.services.adapters.custom_adapter import CustomAdapter


class AdapterFactory:
    """
    Factory class for creating model provider adapters.
    """
    
    # Map of provider names to adapter classes
    _adapter_classes: Dict[str, Type[ModelProviderAdapter]] = {
        "ollama": OllamaAdapter,
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "custom": CustomAdapter
    }
    
    # Cache of adapter instances
    _adapter_instances: Dict[str, ModelProviderAdapter] = {}
    
    @classmethod
    def get_adapter(cls, provider: str) -> ModelProviderAdapter:
        """
        Get an adapter for the specified provider.
        
        Args:
            provider: The name of the provider
            
        Returns:
            An instance of the appropriate ModelProviderAdapter
        """
        # Convert provider name to lowercase for case-insensitive matching
        provider_key = provider.lower()
        
        # Check if we already have an instance for this provider
        if provider_key in cls._adapter_instances:
            return cls._adapter_instances[provider_key]
        
        # Get the adapter class
        adapter_class = cls._adapter_classes.get(provider_key, CustomAdapter)
        
        # Create a new instance
        adapter = adapter_class()
        
        # Cache the instance
        cls._adapter_instances[provider_key] = adapter
        
        return adapter
    
    @classmethod
    def register_adapter(cls, provider: str, adapter_class: Type[ModelProviderAdapter]) -> None:
        """
        Register a new adapter class for a provider.
        
        Args:
            provider: The name of the provider
            adapter_class: The adapter class to use for this provider
        """
        provider_key = provider.lower()
        cls._adapter_classes[provider_key] = adapter_class
        
        # Clear any cached instance
        if provider_key in cls._adapter_instances:
            del cls._adapter_instances[provider_key]
