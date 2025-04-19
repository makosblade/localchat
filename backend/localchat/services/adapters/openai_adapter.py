from typing import Dict, Any, List, Optional

from localchat.models import MessageModel
from localchat.services.adapters.base_adapter import ModelProviderAdapter


class OpenAIAdapter(ModelProviderAdapter):
    """
    Adapter for the OpenAI API.
    """
    
    def format_url(self, base_url: str) -> str:
        """
        Format the base URL for the OpenAI API endpoint.
        
        Args:
            base_url: The base URL provided by the user
            
        Returns:
            The formatted URL for the OpenAI API
        """
        if not base_url:
            return "https://api.openai.com/v1/chat/completions"
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
        Format the request payload for the OpenAI API.
        
        Args:
            model_name: The name of the model to use
            messages: List of previous messages for context
            token_size: Maximum token size for the response
            system_prompt: Optional system prompt to override what's in the Modelfile
            stream: Whether to stream the response
            
        Returns:
            The formatted request payload
        """
        # Format messages for OpenAI API
        formatted_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        # Add system prompt if provided
        if system_prompt:
            formatted_messages.insert(0, {"role": "system", "content": system_prompt})

        # Prepare the OpenAI request payload
        payload = {
            "model": model_name,
            "messages": formatted_messages,
            "max_tokens": token_size,
            "stream": stream
        }
        
        return payload
    
    def extract_response_text(self, response_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract the response text from the OpenAI API response.
        
        Args:
            response_data: The JSON response data from the OpenAI API
            
        Returns:
            The extracted response text, or None if no text could be extracted
        """
        if "choices" in response_data and len(response_data["choices"]) > 0:
            choice = response_data["choices"][0]
            if isinstance(choice, dict):
                if "message" in choice and "content" in choice["message"]:
                    return choice["message"]["content"]
                elif "text" in choice:
                    return choice["text"]
        return None
    
    def extract_streaming_chunk(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract the text from a streaming chunk from the OpenAI API.
        
        Args:
            chunk_data: The JSON data from a streaming chunk
            
        Returns:
            The extracted text, or None if no text could be extracted
        """
        if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
            choice = chunk_data["choices"][0]
            if "delta" in choice and "content" in choice["delta"]:
                return choice["delta"]["content"]
        return None
    
    def is_final_chunk(self, chunk_data: Dict[str, Any]) -> bool:
        """
        Check if this is the final chunk in a streaming response from the OpenAI API.
        
        Args:
            chunk_data: The JSON data from a streaming chunk
            
        Returns:
            True if this is the final chunk, False otherwise
        """
        if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
            return chunk_data["choices"][0].get("finish_reason") is not None
        return False
    
    def get_streaming_stats(self, final_chunk: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract statistics from the final chunk of a streaming response from the OpenAI API.
        
        Args:
            final_chunk: The JSON data from the final streaming chunk
            
        Returns:
            A dictionary of statistics
        """
        stats = {}
        if "usage" in final_chunk:
            usage = final_chunk["usage"]
            if "prompt_tokens" in usage:
                stats["prompt_tokens"] = usage["prompt_tokens"]
            if "completion_tokens" in usage:
                stats["completion_tokens"] = usage["completion_tokens"]
            if "total_tokens" in usage:
                stats["total_tokens"] = usage["total_tokens"]
        return stats
