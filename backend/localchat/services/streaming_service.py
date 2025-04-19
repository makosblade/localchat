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
from localchat.services.interactions.interaction_service import ModelInteractionService
from localchat.models import SessionLocal

# Get logger
logger = logging.getLogger("localchat")

class StreamingService:
    """Service layer for streaming operations."""

    def __init__(
        self,
        db: Session = Depends(get_db_dependency),
        chat_service: ChatService = Depends(ChatService),
        profile_service: ProfileService = Depends(ProfileService),
        interaction_service: ModelInteractionService = Depends(ModelInteractionService)
    ):
        """
        Initializes the StreamingService with database and service dependencies.

        Args:
            db: The SQLAlchemy Session object injected by FastAPI.
            chat_service: The ChatService instance injected by FastAPI.
            profile_service: The ProfileService instance injected by FastAPI.
            interaction_service: The ModelInteractionService instance injected by FastAPI.
        """
        self.db = db
        self.chat_service = chat_service
        self.profile_service = profile_service
        self.interaction_service = interaction_service

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
        try:
            if stream:
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
            else:
                # Use the interaction service to execute a non-streaming interaction
                response_text = await self.interaction_service.execute_non_streaming(
                    url=url,
                    model_name=model_name,
                    messages=messages,
                    provider=provider,
                    token_size=token_size,
                    system_prompt=system_prompt,
                    temperature=temperature
                )
                yield response_text
        except Exception as e:
            # If it's already a ModelAPIException, just re-raise it
            if isinstance(e, ModelAPIException):
                raise
                
            # Otherwise, wrap it in a ModelAPIException
            error_message = f"Error in model interaction: {str(e)}"
            logger.error(error_message, exc_info=True)
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
