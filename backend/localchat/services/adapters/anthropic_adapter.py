from typing import Dict, Any, List, Optional

from localchat.models import MessageModel
from localchat.services.adapters.base_adapter import ModelProviderAdapter


class AnthropicAdapter(ModelProviderAdapter):
    """
    Adapter for the Anthropic API.
    """
    
    def format_url(self, base_url: str) -> str:
        """
        Format the base URL for the Anthropic API endpoint.
        
        Args:
            base_url: The base URL provided by the user
            
        Returns:
            The formatted URL for the Anthropic API
        """
        if not base_url:
            return "https://api.anthropic.com/v1/messages"
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
        Format the request payload for the Anthropic API.
        
        Args:
            model_name: The name of the model to use
            messages: List of previous messages for context
            token_size: Maximum token size for the response
            system_prompt: Optional system prompt to override what's in the Modelfile
            stream: Whether to stream the response
            
        Returns:
            The formatted request payload
        """
        # Format messages for Anthropic API
        system = system_prompt or ""
        messages_content = []

        for msg in messages:
            messages_content.append({
                "role": "user" if msg.role == "user" else "assistant",
                "content": msg.content
            })

        # Prepare the Anthropic request payload
        payload = {
            "model": model_name,
            "messages": messages_content,
            "system": system,
            "max_tokens": token_size,
            "stream": stream
        }
        
        return payload
    
    def extract_response_text(self, response_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract the response text from the Anthropic API response.
        
        Args:
            response_data: The JSON response data from the Anthropic API
            
        Returns:
            The extracted response text, or None if no text could be extracted
        """
        # Anthropic Claude API (newer version)
        if "content" in response_data and isinstance(response_data["content"], list):
            for content_block in response_data["content"]:
                if isinstance(content_block, dict) and content_block.get("type") == "text":
                    return content_block.get("text", "")
                    
        # Anthropic format (older API)
        if "completion" in response_data:
            return response_data["completion"]
            
        return None
    
    def extract_streaming_chunk(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract the text from a streaming chunk from the Anthropic API.
        
        Args:
            chunk_data: The JSON data from a streaming chunk
            
        Returns:
            The extracted text, or None if no text could be extracted
        """
        if "delta" in chunk_data and "text" in chunk_data["delta"]:
            return chunk_data["delta"]["text"]
            
        # Older API format
        if "completion" in chunk_data:
            return chunk_data["completion"]
            
        return None
    
    def is_final_chunk(self, chunk_data: Dict[str, Any]) -> bool:
        """
        Check if this is the final chunk in a streaming response from the Anthropic API.
        
        Args:
            chunk_data: The JSON data from a streaming chunk
            
        Returns:
            True if this is the final chunk, False otherwise
        """
        return chunk_data.get("type") == "message_stop"
    
    def get_streaming_stats(self, final_chunk: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract statistics from the final chunk of a streaming response from the Anthropic API.
        
        Args:
            final_chunk: The JSON data from the final streaming chunk
            
        Returns:
            A dictionary of statistics
        """
        stats = {}
        if "usage" in final_chunk:
            usage = final_chunk["usage"]
            if "input_tokens" in usage:
                stats["prompt_tokens"] = usage["input_tokens"]
            if "output_tokens" in usage:
                stats["completion_tokens"] = usage["output_tokens"]
        return stats
