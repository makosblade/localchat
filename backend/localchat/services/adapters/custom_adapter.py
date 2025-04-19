from typing import Dict, Any, List, Optional

from localchat.models import MessageModel
from localchat.services.adapters.base_adapter import ModelProviderAdapter
from localchat.utils import extract_response_text as utils_extract_response_text


class CustomAdapter(ModelProviderAdapter):
    """
    Default adapter for custom or unknown model providers.
    Uses a generic OpenAI-like format for requests and handles various response formats.
    """
    
    def format_url(self, base_url: str) -> str:
        """
        Format the base URL for a custom API endpoint.
        
        Args:
            base_url: The base URL provided by the user
            
        Returns:
            The formatted URL (unchanged for custom providers)
        """
        return base_url
    
    def format_request_payload(
        self, 
        model_name: str,
        messages: List[MessageModel],
        token_size: int,
        system_prompt: Optional[str] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Format the request payload for a custom API.
        Uses OpenAI-like format as a default.
        
        Args:
            model_name: The name of the model to use
            messages: List of previous messages for context
            token_size: Maximum token size for the response
            system_prompt: Optional system prompt
            stream: Whether to stream the response
            
        Returns:
            The formatted request payload
        """
        # Format messages in OpenAI-like format
        formatted_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        # Add system prompt if provided
        if system_prompt:
            formatted_messages.insert(0, {"role": "system", "content": system_prompt})

        # Prepare a generic request payload
        payload = {
            "model": model_name,
            "messages": formatted_messages,
            "max_tokens": token_size,
            "stream": stream
        }
        
        return payload
    
    def extract_response_text(self, response_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract the response text from various API response formats.
        
        Args:
            response_data: The JSON response data from the model API
            
        Returns:
            The extracted response text, or None if no text could be extracted
        """
        # Use the utility function that handles various formats
        return utils_extract_response_text(response_data)
    
    def extract_streaming_chunk(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract the text from a streaming chunk.
        Attempts to handle various formats.
        
        Args:
            chunk_data: The JSON data from a streaming chunk
            
        Returns:
            The extracted text, or None if no text could be extracted
        """
        # Try OpenAI format
        if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
            choice = chunk_data["choices"][0]
            if "delta" in choice and "content" in choice["delta"]:
                return choice["delta"]["content"]
                
        # Try Ollama format
        if "response" in chunk_data:
            return chunk_data["response"]
            
        # Try Anthropic format
        if "delta" in chunk_data and "text" in chunk_data["delta"]:
            return chunk_data["delta"]["text"]
            
        # Try Anthropic older format
        if "completion" in chunk_data:
            return chunk_data["completion"]
            
        # Try Cohere format
        if "text" in chunk_data:
            return chunk_data["text"]
            
        return None
    
    def is_final_chunk(self, chunk_data: Dict[str, Any]) -> bool:
        """
        Check if this is the final chunk in a streaming response.
        Attempts to handle various formats.
        
        Args:
            chunk_data: The JSON data from a streaming chunk
            
        Returns:
            True if this is the final chunk, False otherwise
        """
        # Try OpenAI format
        if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
            return chunk_data["choices"][0].get("finish_reason") is not None
            
        # Try Ollama format
        if "done" in chunk_data:
            return chunk_data["done"]
            
        # Try Anthropic format
        if "type" in chunk_data:
            return chunk_data["type"] == "message_stop"
            
        return False
    
    def get_streaming_stats(self, final_chunk: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract statistics from the final chunk of a streaming response.
        Attempts to handle various formats.
        
        Args:
            final_chunk: The JSON data from the final streaming chunk
            
        Returns:
            A dictionary of statistics
        """
        stats = {}
        
        # Try OpenAI format
        if "usage" in final_chunk:
            usage = final_chunk["usage"]
            if "prompt_tokens" in usage:
                stats["prompt_tokens"] = usage["prompt_tokens"]
            if "completion_tokens" in usage:
                stats["completion_tokens"] = usage["completion_tokens"]
            if "total_tokens" in usage:
                stats["total_tokens"] = usage["total_tokens"]
                
        # Try Ollama format
        if "eval_count" in final_chunk:
            stats["eval_count"] = final_chunk["eval_count"]
        if "eval_duration" in final_chunk:
            stats["eval_duration"] = final_chunk["eval_duration"]
        if "total_duration" in final_chunk:
            stats["total_duration"] = final_chunk["total_duration"]
            
        return stats
