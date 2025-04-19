import json
import logging
from typing import Optional, List, Dict, Any

import httpx

from localchat.error_handlers import ModelAPIException
from localchat.models import MessageModel
from localchat.services.adapters.base_adapter import ModelProviderAdapter
from localchat.services.interactions.base_strategy import ModelInteractionStrategy

# Get logger
logger = logging.getLogger("localchat")


class NonStreamingInteractionStrategy(ModelInteractionStrategy):
    """
    Strategy for non-streaming interactions with model providers.
    Handles the standard request-response pattern while delegating
    provider-specific formatting to the adapter.
    """
    
    async def execute(
        self, 
        adapter: ModelProviderAdapter,
        url: str,
        model_name: str,
        messages: List[MessageModel],
        token_size: Optional[int],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7
    ) -> str:
        """
        Execute a non-streaming interaction with the model provider.
        
        Args:
            adapter: The provider adapter to use for formatting requests and responses
            url: The API endpoint URL
            model_name: The name of the model to use
            messages: List of previous messages for context
            token_size: Maximum token size for the response
            system_prompt: Optional system prompt to override what's in the Modelfile
            temperature: Temperature parameter for response generation
            
        Returns:
            The model's response text
            
        Raises:
            ModelAPIException: If there's an error communicating with the model API
        """
        # Format the URL using the adapter
        formatted_url = adapter.format_url(url)
        
        # Format the request payload using the adapter
        payload = adapter.format_request_payload(
            model_name=model_name,
            messages=messages,
            token_size=token_size,
            system_prompt=system_prompt,
            stream=False
        )
        
        # Add temperature if provided
        if temperature is not None:
            payload["temperature"] = temperature

        logger.info(
            f"Sending request to model API at {formatted_url}",
            extra={
                "model": model_name,
                "token_size": token_size,
                "message_count": len(messages)
            }
        )

        try:
            # Send the request to the API
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(formatted_url, json=payload)

                # Check if the request was successful
                response.raise_for_status()

                # Parse the response
                response_data = response.json()

                logger.debug(
                    f"Received response from model API",
                    extra={"response_data": json.dumps(response_data)[:1000]}  # Limit log size
                )

                # Extract the response text using the adapter
                response_text = adapter.extract_response_text(response_data)

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
