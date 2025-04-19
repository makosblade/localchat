import logging
from typing import List, Optional, AsyncGenerator

from fastapi import Depends

from ..error_handlers import ModelAPIException
from ..models import MessageModel
from ..services.interactions.interaction_service import ModelInteractionService

logger = logging.getLogger("localchat")


class ModelService:
    """
    Service for direct communication with model APIs (Ollama, OpenAI, etc.), including streaming and response parsing.
    Uses provider-specific adapters and interaction strategies to handle different API formats and interaction patterns.
    """

    def __init__(
        self,
        interaction_service: ModelInteractionService = Depends(ModelInteractionService)
    ):
        """
        Initialize the ModelService with dependencies.
        
        Args:
            interaction_service: The service for executing model interactions
        """
        self.interaction_service = interaction_service

    async def get_model_response(
            self,
            url: str,
            model_name: str,
            messages: List[MessageModel],
            token_size: int,
            provider: str = "custom",
            system_prompt: Optional[str] = None
    ) -> str:
        """
        Send a request to the configured model endpoint and get a response.

        Args:
            url: The API endpoint URL
            model_name: The name of the model to use
            messages: List of previous messages for context
            token_size: Maximum token size for the response
            provider: The provider to use (ollama, openai, anthropic, custom)
            system_prompt: Optional system prompt to override what's in the Modelfile

        Returns:
            The model's response text

        Raises:
            ModelAPIException: If there's an error communicating with the model API
        """
        try:
            # Use the interaction service to execute a non-streaming interaction
            return await self.interaction_service.execute_non_streaming(
                url=url,
                model_name=model_name,
                messages=messages,
                provider=provider,
                token_size=token_size,
                system_prompt=system_prompt
            )
        except Exception as e:
            # If it's already a ModelAPIException, just re-raise it
            if isinstance(e, ModelAPIException):
                raise
                
            # Otherwise, wrap it in a ModelAPIException
            error_message = f"Error getting model response: {str(e)}"
            logger.error(error_message, exc_info=True)
            raise ModelAPIException(
                detail=error_message,
                original_exception=e
            )
            
    async def stream_model_response(
        self,
        url: str,
        model_name: str,
        messages: List[MessageModel],
        token_size: Optional[int] = None,
        provider: str = "ollama",
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> AsyncGenerator[str, None]:
        """
        Stream a response from a model provider.
        
        Args:
            url: The API endpoint URL
            model_name: The name of the model to use
            messages: List of previous messages for context
            token_size: Maximum token size for the response
            provider: The provider to use (ollama, openai, anthropic, custom)
            system_prompt: Optional system prompt to override what's in the Modelfile
            temperature: Temperature parameter for response generation
            
        Yields:
            Chunks of the streaming response
            
        Raises:
            ModelAPIException: If there's an error communicating with the model API
        """
        try:
            # Use the interaction service to execute a streaming interaction
            async for chunk in self.interaction_service.execute_streaming(
                url=url,
                model_name=model_name,
                messages=messages,
                provider=provider,
                token_size=token_size,
                system_prompt=system_prompt,
                temperature=temperature
            ):
                yield chunk
        except Exception as e:
            # If it's already a ModelAPIException, just re-raise it
            if isinstance(e, ModelAPIException):
                raise
                
            # Otherwise, wrap it in a ModelAPIException
            error_message = f"Error streaming model response: {str(e)}"
            logger.error(error_message, exc_info=True)
            raise ModelAPIException(
                detail=error_message,
                original_exception=e
            )
