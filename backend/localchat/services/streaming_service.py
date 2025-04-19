from typing import Dict, Any, AsyncGenerator, List, Optional
import logging
import json
import asyncio
import uuid
from fastapi import Depends, HTTPException
from fastapi.responses import StreamingResponse
import httpx
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from localchat.models import MessageModel, ProfileModel
from localchat.error_handlers import ModelAPIException
from localchat.utils import get_db_dependency
from localchat.exceptions import (
    MessageCreationError,
    DatabaseOperationError,
    ChatNotFoundError,
    ProfileNotFoundError
)
from localchat.services.chat_service import ChatService
from localchat.services.profile_service import ProfileService
from localchat.models import SessionLocal

# Get logger
logger = logging.getLogger("localchat")

class StreamingService:
    """Service layer for streaming operations."""

    def __init__(
        self,
        db: Session = Depends(get_db_dependency),
        chat_service: ChatService = Depends(ChatService),
        profile_service: ProfileService = Depends(ProfileService)
    ):
        """
        Initializes the StreamingService with database and service dependencies.

        Args:
            db: The SQLAlchemy Session object injected by FastAPI.
            chat_service: The ChatService instance injected by FastAPI.
            profile_service: The ProfileService instance injected by FastAPI.
        """
        self.db = db
        self.chat_service = chat_service
        self.profile_service = profile_service

    async def create_streaming_response_for_chat(
        self,
        chat_id: int,
        messages: List[MessageModel],
        profile: ProfileModel,
        request_id: str = None
    ) -> StreamingResponse:
        """
        Creates a streaming response for a chat.

        Args:
            chat_id: The ID of the chat.
            messages: List of previous messages for context.
            profile: The profile with model configuration.
            request_id: Optional request ID for logging.

        Returns:
            StreamingResponse object for FastAPI.

        Raises:
            ModelAPIException: If there's an error communicating with the model API.
            MessageCreationError: If there's an error creating the message.
        """
        if request_id is None:
            request_id = str(uuid.uuid4())

        try:
            # Create a new empty message to be filled with the streamed content
            assistant_message = MessageModel(
                chat_id=chat_id,
                role="assistant",
                content=""  # Will be filled after streaming completes
            )
            self.db.add(assistant_message)
            self.db.commit()
            self.db.refresh(assistant_message)
            
            logger.info(
                f"Created empty assistant message (ID: {assistant_message.id}) for streaming in chat {chat_id}",
                extra={
                    "request_id": request_id,
                    "message_id": assistant_message.id,
                    "streaming": True
                }
            )
            
            # Create a generator for the streaming response
            response_generator = self.stream_model_response(
                url=profile.url,
                model_name=profile.model_name,
                messages=messages,
                token_size=profile.token_size,
                provider=profile.provider or "ollama"
            )
            
            # Create a background task to save the complete response
            asyncio.create_task(
                self._save_streaming_response(
                    message_id=assistant_message.id,
                    url=profile.url,
                    model_name=profile.model_name,
                    messages=messages,
                    token_size=profile.token_size,
                    provider=profile.provider or "custom",
                    request_id=request_id
                )
            )
            
            # Return the streaming response
            return self.create_streaming_response(response_generator)
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error creating streaming message: {str(e)}",
                extra={"request_id": request_id},
                exc_info=True
            )
            raise MessageCreationError(
                "Failed to create streaming message due to database error",
                original_exception=e
            )
        except Exception as e:
            logger.error(
                f"Error setting up streaming response: {str(e)}",
                extra={"request_id": request_id},
                exc_info=True
            )
            raise ModelAPIException(
                detail=f"Error setting up streaming response: {str(e)}",
                original_exception=e
            )

    async def _save_streaming_response(
        self,
        message_id: int,
        url: str,
        model_name: str,
        messages: List[MessageModel],
        token_size: Optional[int] = None,
        provider: str = "custom",
        request_id: str = None
    ) -> None:
        """
        Save the complete response for a streaming message.

        Args:
            message_id: The ID of the message to update.
            url: The API endpoint URL.
            model_name: The name of the model to use.
            messages: List of previous messages for context.
            token_size: Maximum token size for the response.
            provider: The provider name.
            request_id: Optional request ID for logging.
        """
        if request_id is None:
            request_id = str(uuid.uuid4())
            
        try:
            full_response = ""
            async for chunk in self.stream_model_response(
                url=url,
                model_name=model_name,
                messages=messages,
                token_size=token_size,
                provider=provider,
                stream=False  # Get the full response in one go
            ):
                full_response += chunk
            
            # Create a new session for the background task
            # to avoid session conflicts
            bg_db = SessionLocal()
            try:
                # Update the message with the complete response
                db_message = bg_db.query(MessageModel).filter(
                    MessageModel.id == message_id
                ).first()
                
                if db_message and full_response.strip():
                    db_message.content = full_response
                    bg_db.commit()
                    
                    logger.info(
                        f"Updated assistant message (ID: {message_id}) with complete response",
                        extra={
                            "request_id": request_id,
                            "message_id": message_id,
                            "content_length": len(full_response)
                        }
                    )
                else:
                    logger.warning(
                        f"Could not update assistant message (ID: {message_id}) - "
                        f"Message not found or empty response",
                        extra={
                            "request_id": request_id,
                            "message_id": message_id,
                            "found": db_message is not None,
                            "response_length": len(full_response) if full_response else 0
                        }
                    )
            except Exception as e:
                logger.error(
                    f"Error saving complete response for message {message_id}: {str(e)}",
                    extra={"request_id": request_id},
                    exc_info=True
                )
            finally:
                bg_db.close()
        except Exception as e:
            logger.error(
                f"Error in background task for message {message_id}: {str(e)}",
                extra={"request_id": request_id},
                exc_info=True
            )

    async def save_streaming_response(
        self,
        message_id: int,
        response_text: str,
        request_id: str = None
    ) -> None:
        """
        Save or update a response for a streaming message.

        Args:
            message_id: The ID of the message to update.
            response_text: The response text to save.
            request_id: Optional request ID for logging.
        
        Raises:
            MessageCreationError: If there's an error updating the message.
        """
        if request_id is None:
            request_id = str(uuid.uuid4())
            
        try:
            # Create a new session for this operation
            # to avoid conflicts with other operations
            save_db = SessionLocal()
            try:
                # Update the message with the response text
                db_message = save_db.query(MessageModel).filter(
                    MessageModel.id == message_id
                ).first()
                
                if db_message and response_text.strip():
                    db_message.content = response_text
                    save_db.commit()
                    
                    logger.info(
                        f"Updated streaming message (ID: {message_id}) with response",
                        extra={
                            "request_id": request_id,
                            "message_id": message_id,
                            "content_length": len(response_text)
                        }
                    )
                else:
                    logger.warning(
                        f"Could not update streaming message (ID: {message_id}) - "
                        f"Message not found or empty response",
                        extra={
                            "request_id": request_id,
                            "message_id": message_id,
                            "found": db_message is not None,
                            "response_length": len(response_text) if response_text else 0
                        }
                    )
            except SQLAlchemyError as e:
                save_db.rollback()
                logger.error(
                    f"Database error updating streaming message {message_id}: {str(e)}",
                    extra={"request_id": request_id},
                    exc_info=True
                )
                raise MessageCreationError(
                    f"Failed to update streaming message {message_id} due to database error",
                    original_exception=e
                )
            finally:
                save_db.close()
        except Exception as e:
            logger.error(
                f"Unexpected error updating streaming message {message_id}: {str(e)}",
                extra={"request_id": request_id},
                exc_info=True
            )
            raise MessageCreationError(
                f"Failed to update streaming message {message_id} due to unexpected error",
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
        temperature: float = 0.7,
        stream: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Stream a response from the model API.
        
        Args:
            url: The base URL of the model API
            model_name: The name of the model to use
            messages: List of previous messages for context
            token_size: Maximum token size for the response (optional)
            provider: The provider name (ollama, openai, anthropic, custom)
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
            f"Starting streaming request to model API",
            extra={
                "request_id": request_id,
                "model": model_name,
                "provider": provider,
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
                            f"Model API returned error: {response.status_code}",
                            extra={
                                "request_id": request_id,
                                "status_code": response.status_code,
                                "error": error_text
                            }
                        )
                        raise ModelAPIException(
                            detail=f"Model API error: {error_text}",
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
                                    if chunk_data["choices"][0].get("finish_reason") is not None:
                                        logger.info(
                                            f"Completed streaming response from {provider}",
                                            extra={
                                                "request_id": request_id,
                                                "finish_reason": chunk_data["choices"][0].get("finish_reason"),
                                                "response_length": len(full_response)
                                            }
                                        )
                            elif provider == "anthropic":
                                # Anthropic streaming format
                                if "delta" in chunk_data and "text" in chunk_data["delta"]:
                                    response_text = chunk_data["delta"]["text"]
                                    
                                    # Check if this is the final chunk
                                    if chunk_data.get("type") == "message_stop":
                                        logger.info(
                                            f"Completed streaming response from {provider}",
                                            extra={
                                                "request_id": request_id,
                                                "response_length": len(full_response)
                                            }
                                        )
                            else:
                                # Generic format - try to extract text from the chunk
                                if "text" in chunk_data:
                                    response_text = chunk_data["text"]
                                elif "content" in chunk_data:
                                    response_text = chunk_data["content"]
                                elif "response" in chunk_data:
                                    response_text = chunk_data["response"]
                            
                            # Yield the response text
                            if response_text:
                                full_response += response_text
                                yield response_text
                                
                        except json.JSONDecodeError:
                            # Some APIs might return non-JSON data
                            if chunk.strip():
                                full_response += chunk
                                yield chunk
                        except Exception as e:
                            logger.error(
                                f"Error processing chunk: {str(e)}",
                                extra={"request_id": request_id},
                                exc_info=True
                            )
                            # Continue processing other chunks
                            continue
        except httpx.RequestError as e:
            # Handle network/connection errors
            error_message = f"Error connecting to model API: {str(e)}"
            logger.error(
                error_message,
                extra={"request_id": request_id},
                exc_info=True
            )
            raise ModelAPIException(
                detail=error_message,
                original_exception=e
            )
        except Exception as e:
            # Handle any other unexpected errors
            error_message = f"Unexpected error in streaming response: {str(e)}"
            logger.error(
                error_message,
                extra={"request_id": request_id},
                exc_info=True
            )
            raise ModelAPIException(
                detail=error_message,
                original_exception=e
            )

    def create_streaming_response(
        self,
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
