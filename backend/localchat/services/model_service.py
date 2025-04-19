import json
import logging
from typing import List, Optional, AsyncGenerator

import httpx

from ..error_handlers import ModelAPIException
from ..models import MessageModel
from ..utils import extract_response_text

logger = logging.getLogger("localchat")

class ModelService:

    async def get_model_response(
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

        Returns:
            The model's response text

        Raises:
            ModelAPIException: If there's an error communicating with the model API
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
                "max_length": token_size
            }
        elif provider == "openai":
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
                "max_tokens": token_size
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
                "max_tokens": token_size
            }
        else:  # custom or unknown provider
            # Format messages for a generic API (OpenAI-like format)
            formatted_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]

            # Prepare a generic request payload
            payload = {
                "model": model_name,
                "messages": formatted_messages,
                "max_tokens": token_size
            }

        logger.info(
            f"Sending request to model API at {url}",
            extra={
                "model": model_name,
                "token_size": token_size,
                "message_count": len(messages)
            }
        )

        try:
            # Send the request to the API
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload)

                # Check if the request was successful
                response.raise_for_status()

                # Parse the response
                response_data = response.json()

                logger.debug(
                    f"Received response from model API",
                    extra={"response_data": json.dumps(response_data)[:1000]}  # Limit log size
                )

                # Extract the response text based on the API format
                response_text = extract_response_text(response_data)

                if response_text:
                    return response_text
                else:
                    # If we can't extract the response text, raise an exception
                    raise ModelAPIException(
                        detail="Unable to parse model response",
                        response_data=response_data
                    )

        except httpx.HTTPStatusError as e:
            # Handle HTTP errors from the model API
            error_message = f"Model API returned error status: {e.response.status_code}"

            try:
                error_data = e.response.json()
                error_detail = error_data.get("error", {}).get("message", str(e))
            except:
                error_detail = e.response.text[:500] if e.response.text else str(e)

            logger.error(
                f"HTTP error from model API: {error_message}",
                extra={
                    "status_code": e.response.status_code,
                    "error_detail": error_detail
                }
            )

            raise ModelAPIException(
                detail=f"Error from model API: {error_detail}",
                original_exception=e
            )

        except httpx.RequestError as e:
            # Handle network/connection errors
            error_message = f"Error connecting to model API: {str(e)}"
            logger.error(error_message)
            raise ModelAPIException(
                detail=error_message,
                original_exception=e
            )

        except Exception as e:
            # Handle any other unexpected errors
            error_message = f"Unexpected error communicating with model API: {str(e)}"
            logger.error(error_message, exc_info=True)
            raise ModelAPIException(
                detail=error_message,
                original_exception=e
            )
