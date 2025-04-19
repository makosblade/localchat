from typing import Dict, Any, List, Optional

from localchat.models import MessageModel
from localchat.services.adapters.base_adapter import ModelProviderAdapter


class OllamaAdapter(ModelProviderAdapter):
    """
    Adapter for the Ollama API.
    """
    
    def format_url(self, base_url: str) -> str:
        """
        Format the base URL for the Ollama API endpoint.
        
        Args:
            base_url: The base URL provided by the user
            
        Returns:
            The formatted URL for the Ollama API
        """
        # Ensure the URL points to the generate endpoint for Ollama
        if not base_url.endswith("/api/generate"):
            # If URL is just the base Ollama URL, append the endpoint
            if base_url.endswith("/"):
                return f"{base_url}api/generate"
            else:
                return f"{base_url}/api/generate"
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
        Format the request payload for the Ollama API.
        
        Args:
            model_name: The name of the model to use
            messages: List of previous messages for context
            token_size: Maximum token size for the response
            system_prompt: Optional system prompt to override what's in the Modelfile
            stream: Whether to stream the response
            
        Returns:
            The formatted request payload
        """
        # Format the prompt based on the conversation history for Ollama
        prompt = ""

        # Add previous messages to provide context
        for msg in messages:
            role_prefix = "User: " if msg.role == "user" else "Assistant: "
            prompt += f"{role_prefix}{msg.content}\n\n"

        # Add the final prompt for the assistant to respond to
        prompt += "Assistant: "

        # Prepare the Ollama request payload
        payload = {
            "model": model_name,
            "prompt": prompt,
            "max_length": token_size,
            "stream": stream
        }
        
        # Add system prompt if provided
        if system_prompt:
            payload["system"] = system_prompt
            
        return payload
    
    def extract_response_text(self, response_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract the response text from the Ollama API response.
        
        Args:
            response_data: The JSON response data from the Ollama API
            
        Returns:
            The extracted response text, or None if no text could be extracted
        """
        if "response" in response_data:
            return response_data["response"]
        return None
    
    def extract_streaming_chunk(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract the text from a streaming chunk from the Ollama API.
        
        Args:
            chunk_data: The JSON data from a streaming chunk
            
        Returns:
            The extracted text, or None if no text could be extracted
        """
        if "response" in chunk_data:
            return chunk_data["response"]
        return None
    
    def is_final_chunk(self, chunk_data: Dict[str, Any]) -> bool:
        """
        Check if this is the final chunk in a streaming response from the Ollama API.
        
        Args:
            chunk_data: The JSON data from a streaming chunk
            
        Returns:
            True if this is the final chunk, False otherwise
        """
        return chunk_data.get("done", False)
    
    def get_streaming_stats(self, final_chunk: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract statistics from the final chunk of a streaming response from the Ollama API.
        
        Args:
            final_chunk: The JSON data from the final streaming chunk
            
        Returns:
            A dictionary of statistics
        """
        stats = {}
        if "eval_count" in final_chunk:
            stats["eval_count"] = final_chunk["eval_count"]
        if "eval_duration" in final_chunk:
            stats["eval_duration"] = final_chunk["eval_duration"]
        if "total_duration" in final_chunk:
            stats["total_duration"] = final_chunk["total_duration"]
        if "load_duration" in final_chunk:
            stats["load_duration"] = final_chunk["load_duration"]
        return stats
