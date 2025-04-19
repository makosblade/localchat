from typing import Dict, Any, AsyncGenerator, List, Optional
import logging
import json
import asyncio
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
import httpx

from .models import MessageModel
from .error_handlers import ModelAPIException

# Get logger
logger = logging.getLogger("localchat")

async def stream_model_response(
    url: str,
    model_name: str,
    messages: List[MessageModel],
    token_size: Optional[int] = None,
    provider: str = "ollama",  # Added provider parameter
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    stream: bool = True
) -> AsyncGenerator[str, None]:
    """
    Stream a response from the Ollama API.
    
    Args:
        url: The base URL of the Ollama API
        model_name: The name of the model to use
        messages: List of previous messages for context
        token_size: Maximum token size for the response (optional)
        system_prompt: System prompt to override what's in the Modelfile (optional)
        temperature: Temperature parameter for generation randomness
        stream: Whether to stream the response
        
    Yields:
        Chunks of the generated response text
    """
    # Handle provider-specific URL formatting
    if provider == "ollama":
        # Ensure the URL points to the generate endpoint for Ollama
        if not url.endswith("/api/generate"):
            # If URL is just the base Ollama URL, append the endpoint
            if url.endswith("/"):
                url = f"{url}api/generate"
            else:
                url = f"{url}/api/generate"
    elif provider == "openai" and not url:
        # Default OpenAI URL
        url = "https://api.openai.com/v1/chat/completions"
    elif provider == "anthropic" and not url:
        # Default Anthropic URL
        url = "https://api.anthropic.com/v1/messages"
    
    # Prepare the request payload based on provider
    if provider == "ollama":
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
            "stream": stream
        }
    elif provider == "openai":
        # Format messages for OpenAI API
        formatted_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        # Prepare the OpenAI request payload
        payload = {
            "model": model_name,
            "messages": formatted_messages,
            "stream": stream
        }
    elif provider == "anthropic":
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
            "stream": stream
        }
    else:  # custom or unknown provider
        # Use a generic format similar to OpenAI
        formatted_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        # Prepare a generic request payload
        payload = {
            "model": model_name,
            "messages": formatted_messages,
            "stream": stream
        }
    
    # Add optional parameters if provided
    if token_size:
        payload["options"] = {"num_predict": token_size}
    
    if system_prompt:
        payload["system"] = system_prompt
        
    if temperature != 0.7:
        if "options" not in payload:
            payload["options"] = {}
        payload["options"]["temperature"] = temperature
    
    request_id = id(messages)  # Generate a unique ID for this request
    
    logger.info(
        f"Starting streaming request to Ollama API",
        extra={
            "request_id": request_id,
            "model": model_name,
            "url": url,
            "message_count": len(messages),
            "stream": stream
        }
    )
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                # Check if the request was successful
                if response.status_code != 200:
                    error_text = await response.text()
                    logger.error(
                        f"Ollama API returned error: {response.status_code}",
                        extra={
                            "request_id": request_id,
                            "status_code": response.status_code,
                            "error": error_text
                        }
                    )
                    raise ModelAPIException(
                        detail=f"Ollama API error: {error_text}",
                        status_code=response.status_code
                    )
                
                # Process the streaming response based on provider
                full_response = ""
                async for chunk in response.aiter_text():
                    try:
                        # Parse the chunk as JSON
                        chunk_data = json.loads(chunk)
                        response_text = ""
                        
                        # Extract the response text based on provider format
                        if provider == "ollama":
                            response_text = chunk_data.get("response", "")
                            
                            # Log completion if this is the final chunk
                            if chunk_data.get("done", False):
                                # Extract statistics from the final response
                                eval_count = chunk_data.get("eval_count", 0)
                                eval_duration = chunk_data.get("eval_duration", 0)
                                
                                # Calculate tokens per second if available
                                tokens_per_second = 0
                                if eval_duration > 0:
                                    tokens_per_second = (eval_count / eval_duration) * 1_000_000_000
                                
                                logger.info(
                                    f"Completed streaming response from {provider}",
                                    extra={
                                        "request_id": request_id,
                                        "total_tokens": eval_count,
                                        "tokens_per_second": round(tokens_per_second, 2),
                                        "response_length": len(full_response)
                                    }
                                )
                        elif provider == "openai":
                            # OpenAI streaming format
                            if "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                                delta = chunk_data["choices"][0].get("delta", {})
                                response_text = delta.get("content", "")
                                
                                # Check if this is the final chunk
                                if chunk_data.get("choices", [{}])[0].get("finish_reason") is not None:
                                    logger.info(
                                        f"Completed streaming response from {provider}",
                                        extra={
                                            "request_id": request_id,
                                            "response_length": len(full_response)
                                        }
                                    )
                        elif provider == "anthropic":
                            # Anthropic streaming format
                            if "type" in chunk_data and chunk_data["type"] == "content_block_delta":
                                delta = chunk_data.get("delta", {})
                                response_text = delta.get("text", "")
                                
                            # Check if this is the final chunk
                            if "type" in chunk_data and chunk_data["type"] == "message_stop":
                                logger.info(
                                    f"Completed streaming response from {provider}",
                                    extra={
                                        "request_id": request_id,
                                        "response_length": len(full_response)
                                    }
                                )
                        else:  # custom or unknown provider
                            # Try to extract text from common formats
                            if "text" in chunk_data:
                                response_text = chunk_data["text"]
                            elif "content" in chunk_data:
                                response_text = chunk_data["content"]
                            elif "response" in chunk_data:
                                response_text = chunk_data["response"]
                            elif "message" in chunk_data:
                                response_text = chunk_data["message"]
                            elif "choices" in chunk_data and len(chunk_data["choices"]) > 0:
                                choice = chunk_data["choices"][0]
                                if isinstance(choice, dict):
                                    if "text" in choice:
                                        response_text = choice["text"]
                                    elif "message" in choice and "content" in choice["message"]:
                                        response_text = choice["message"]["content"]
                        
                        # Update the full response
                        full_response += response_text
                        
                        # Yield the response text chunk
                        yield response_text
                        
                    except json.JSONDecodeError:
                        logger.warning(
                            f"Failed to parse JSON from Ollama API chunk",
                            extra={"request_id": request_id, "chunk": chunk[:100]}
                        )
                        # Skip invalid JSON chunks
                        continue
                    
    except httpx.RequestError as e:
        logger.error(
            f"Error connecting to Ollama API: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise ModelAPIException(
            detail=f"Error connecting to Ollama API: {str(e)}",
            original_exception=e
        )
    except Exception as e:
        logger.error(
            f"Unexpected error during Ollama API streaming: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise ModelAPIException(
            detail=f"Unexpected error during streaming: {str(e)}",
            original_exception=e
        )

def create_streaming_response(
    generator: AsyncGenerator[str, None]
) -> StreamingResponse:
    """
    Create a FastAPI StreamingResponse from an async generator.
    
    Args:
        generator: Async generator that yields response chunks
        
    Returns:
        StreamingResponse object for FastAPI
    """
    async def stream_response():
        async for chunk in generator:
            # Format each chunk as a Server-Sent Event
            yield f"data: {chunk}\n\n"
    
    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering in Nginx
        }
    )
