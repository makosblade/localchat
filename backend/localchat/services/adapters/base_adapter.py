from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod

from localchat.models import MessageModel


class ModelProviderAdapter(ABC):
    """
    Base adapter class for model providers.
    Defines the interface that all provider adapters must implement.
    """
    
    @abstractmethod
    def format_url(self, base_url: str) -> str:
        """
        Format the base URL for the provider's API endpoint.
        
        Args:
            base_url: The base URL provided by the user
            
        Returns:
            The formatted URL for the provider's API
        """
        pass
    
    @abstractmethod
    def format_request_payload(
        self, 
        model_name: str,
        messages: List[MessageModel],
        token_size: int,
        system_prompt: Optional[str] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Format the request payload for the provider's API.
        
        Args:
            model_name: The name of the model to use
            messages: List of previous messages for context
            token_size: Maximum token size for the response
            system_prompt: Optional system prompt to override what's in the Modelfile
            stream: Whether to stream the response
            
        Returns:
            The formatted request payload
        """
        pass
    
    @abstractmethod
    def extract_response_text(self, response_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract the response text from the provider's API response.
        
        Args:
            response_data: The JSON response data from the model API
            
        Returns:
            The extracted response text, or None if no text could be extracted
        """
        pass
    
    @abstractmethod
    def extract_streaming_chunk(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract the text from a streaming chunk.
        
        Args:
            chunk_data: The JSON data from a streaming chunk
            
        Returns:
            The extracted text, or None if no text could be extracted
        """
        pass
    
    @abstractmethod
    def is_final_chunk(self, chunk_data: Dict[str, Any]) -> bool:
        """
        Check if this is the final chunk in a streaming response.
        
        Args:
            chunk_data: The JSON data from a streaming chunk
            
        Returns:
            True if this is the final chunk, False otherwise
        """
        pass
    
    @abstractmethod
    def get_streaming_stats(self, final_chunk: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract statistics from the final chunk of a streaming response.
        
        Args:
            final_chunk: The JSON data from the final streaming chunk
            
        Returns:
            A dictionary of statistics
        """
        pass
