from abc import ABC, abstractmethod
from typing import AsyncGenerator, Any, Optional, List

from localchat.models import MessageModel
from localchat.services.adapters.base_adapter import ModelProviderAdapter


class ModelInteractionStrategy(ABC):
    """
    Abstract base class for model interaction strategies.
    Defines the interface that all interaction strategies must implement.
    """
    
    @abstractmethod
    async def execute(
        self, 
        adapter: ModelProviderAdapter,
        url: str,
        model_name: str,
        messages: List[MessageModel],
        token_size: Optional[int],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> Any:
        """
        Execute the interaction strategy with the given adapter and parameters.
        
        Args:
            adapter: The provider adapter to use for formatting requests and responses
            url: The API endpoint URL
            model_name: The name of the model to use
            messages: List of previous messages for context
            token_size: Maximum token size for the response
            system_prompt: Optional system prompt to override what's in the Modelfile
            temperature: Temperature parameter for response generation
            
        Returns:
            The result of the interaction, which depends on the specific strategy
        """
        pass
