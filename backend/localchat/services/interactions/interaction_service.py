import logging
from typing import AsyncGenerator, Optional, List

from fastapi import Depends

from localchat.models import MessageModel
from localchat.services.adapters.adapter_factory import AdapterFactory
from localchat.services.adapters.base_adapter import ModelProviderAdapter
from localchat.services.interactions.streaming_strategy import StreamingInteractionStrategy
from localchat.services.interactions.non_streaming_strategy import NonStreamingInteractionStrategy

# Get logger
logger = logging.getLogger("localchat")


class ModelInteractionService:
    """
    Service for executing model interaction strategies.
    Orchestrates the interaction between adapters and strategies.
    """
    
    def __init__(
        self,
        streaming_strategy: StreamingInteractionStrategy = Depends(StreamingInteractionStrategy),
        non_streaming_strategy: NonStreamingInteractionStrategy = Depends(NonStreamingInteractionStrategy)
    ):
        """
        Initialize the ModelInteractionService with strategies.
        
        Args:
            streaming_strategy: The strategy for streaming interactions
            non_streaming_strategy: The strategy for non-streaming interactions
        """
        self.streaming_strategy = streaming_strategy
        self.non_streaming_strategy = non_streaming_strategy
    
    async def execute_streaming(
        self,
        url: str,
        model_name: str,
        messages: List[MessageModel],
        provider: str = "custom",
        token_size: Optional[int] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """
        Execute a streaming interaction with the model provider.
        
        Args:
            url: The API endpoint URL
            model_name: The name of the model to use
            messages: List of previous messages for context
            provider: The provider name (ollama, openai, anthropic, custom)
            token_size: Maximum token size for the response
            system_prompt: Optional system prompt to override what's in the Modelfile
            temperature: Temperature parameter for response generation
            
        Yields:
            Chunks of the streaming response
        """
        # Get the appropriate adapter for this provider
        adapter = AdapterFactory.get_adapter(provider)
        
        # Execute the streaming strategy
        async for chunk in self.streaming_strategy.execute(
            adapter=adapter,
            url=url,
            model_name=model_name,
            messages=messages,
            token_size=token_size,
            system_prompt=system_prompt,
            temperature=temperature
        ):
            yield chunk
    
    async def execute_non_streaming(
        self,
        url: str,
        model_name: str,
        messages: List[MessageModel],
        provider: str = "custom",
        token_size: Optional[int] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Execute a non-streaming interaction with the model provider.
        
        Args:
            url: The API endpoint URL
            model_name: The name of the model to use
            messages: List of previous messages for context
            provider: The provider name (ollama, openai, anthropic, custom)
            token_size: Maximum token size for the response
            system_prompt: Optional system prompt to override what's in the Modelfile
            temperature: Temperature parameter for response generation
            
        Returns:
            The model's response text
        """
        # Get the appropriate adapter for this provider
        adapter = AdapterFactory.get_adapter(provider)
        
        # Execute the non-streaming strategy
        return await self.non_streaming_strategy.execute(
            adapter=adapter,
            url=url,
            model_name=model_name,
            messages=messages,
            token_size=token_size,
            system_prompt=system_prompt,
            temperature=temperature
        )
