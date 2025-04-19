import logging
import uuid
import asyncio
from typing import List, Optional, Dict, Any

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from localchat.models import MessageModel, MessageCreate, ChatModel, ProfileModel
from localchat.utils import get_db_dependency
from localchat.exceptions import (
    MessageCreationError,
    MessageFetchError,
    ChatNotFoundError,
    ProfileNotFoundError,
    DatabaseOperationError
)
from localchat.error_handlers import ModelAPIException
from localchat.streaming import stream_model_response, create_streaming_response
from localchat.services.chat_service import ChatService
from localchat.services.profile_service import ProfileService

# Import get_model_response from wherever it's defined
# This might be from model_service.py or another location
from localchat.services.model_service import ModelService

logger = logging.getLogger("localchat")

class MessageService:
    """Service layer for message operations."""

    def __init__(
        self,
        db: Session = Depends(get_db_dependency),
        chat_service: ChatService = Depends(ChatService),
        profile_service: ProfileService = Depends(ProfileService),
        model_service: ModelService = Depends(ModelService)
    ):
        """
        Initializes the MessageService with database and service dependencies.

        Args:
            db: The SQLAlchemy Session object injected by FastAPI.
            chat_service: The ChatService instance injected by FastAPI.
            profile_service: The ProfileService instance injected by FastAPI.
            model_service: The ModelService instance injected by FastAPI.
        """
        self.db = db
        self.chat_service = chat_service
        self.profile_service = profile_service
        self.model_service = model_service

    def get_messages(
        self, 
        chat_id: int, 
        skip: int = 0, 
        limit: int = 100,
        request_id: str = None
    ) -> List[MessageModel]:
        """
        Retrieves messages for a specific chat with pagination.

        Args:
            chat_id: The ID of the chat to retrieve messages for.
            skip: Number of messages to skip.
            limit: Maximum number of messages to return.
            request_id: Optional request ID for logging.

        Returns:
            A list of MessageModel objects.

        Raises:
            ChatNotFoundError: If the chat with the given ID does not exist.
            MessageFetchError: If there's an error fetching messages.
        """
        if request_id is None:
            request_id = str(uuid.uuid4())
            
        logger.info(
            f"Fetching messages for chat ID: {chat_id}",
            extra={
                "request_id": request_id,
                "chat_id": chat_id,
                "skip": skip,
                "limit": limit
            }
        )
        
        try:
            # Verify chat exists
            chat = self.db.query(ChatModel).filter(ChatModel.id == chat_id).first()
            if not chat:
                logger.warning(
                    f"Attempted to fetch messages for non-existent chat: {chat_id}",
                    extra={"request_id": request_id}
                )
                raise ChatNotFoundError(f"Chat with ID {chat_id} not found")
            
            messages = self.db.query(MessageModel).filter(
                MessageModel.chat_id == chat_id
            ).order_by(MessageModel.created_at).offset(skip).limit(limit).all()
            
            logger.info(
                f"Successfully fetched {len(messages)} messages for chat ID: {chat_id}",
                extra={"request_id": request_id, "count": len(messages)}
            )
            
            return messages
        except SQLAlchemyError as e:
            logger.error(
                f"Database error fetching messages: {str(e)}",
                extra={"request_id": request_id},
                exc_info=True
            )
            raise MessageFetchError(
                f"Failed to fetch messages for chat {chat_id} due to database error",
                original_exception=e
            )

    async def create_message(
        self, 
        chat_id: int, 
        message_data: MessageCreate, 
        stream: bool = False,
        request_id: str = None
    ) -> MessageModel:
        """
        Creates a new message in a chat and generates an AI response.

        Args:
            chat_id: The ID of the chat to create the message in.
            message_data: The data for the new message.
            stream: Whether to stream the AI response.
            request_id: Optional request ID for logging.

        Returns:
            The newly created MessageModel object (AI response).

        Raises:
            ChatNotFoundError: If the chat with the given ID does not exist.
            ProfileNotFoundError: If the profile associated with the chat does not exist.
            MessageCreationError: If the message cannot be created due to a database error.
            ModelAPIException: If there's an error communicating with the model API.
        """
        if request_id is None:
            request_id = str(uuid.uuid4())
            
        logger.info(
            f"Creating new message in chat ID: {chat_id}",
            extra={
                "request_id": request_id,
                "chat_id": chat_id,
                "message_role": message_data.role,
                "content_length": len(message_data.content),
                "stream": stream
            }
        )
        
        try:
            # Verify that the chat exists
            chat = self.db.query(ChatModel).filter(ChatModel.id == chat_id).first()
            if not chat:
                logger.warning(
                    f"Attempted to create message in non-existent chat: {chat_id}",
                    extra={"request_id": request_id}
                )
                raise ChatNotFoundError(f"Chat with ID {chat_id} not found")
            
            # Save user message
            db_message = MessageModel(**message_data.dict(), chat_id=chat_id)
            self.db.add(db_message)
            self.db.commit()
            self.db.refresh(db_message)
            
            logger.info(
                f"Saved user message (ID: {db_message.id}) in chat {chat_id}",
                extra={
                    "request_id": request_id,
                    "message_id": db_message.id
                }
            )
            
            # Get profile information
            profile = self.db.query(ProfileModel).filter(ProfileModel.id == chat.profile_id).first()
            if not profile:
                logger.error(
                    f"Profile not found for chat {chat_id} (profile_id: {chat.profile_id})",
                    extra={
                        "request_id": request_id,
                        "chat_id": chat_id,
                        "profile_id": chat.profile_id
                    }
                )
                raise ProfileNotFoundError(f"Profile with ID {chat.profile_id} not found for this chat")
            
            # Get previous messages for context
            previous_messages = self.db.query(MessageModel).filter(
                MessageModel.chat_id == chat_id
            ).order_by(MessageModel.created_at).all()
            
            logger.info(
                f"Sending request to model API for chat {chat_id}",
                extra={
                    "request_id": request_id,
                    "profile_name": profile.name,
                    "model_name": profile.model_name,
                    "url": profile.url,
                    "token_size": profile.token_size,
                    "message_count": len(previous_messages)
                }
            )
            
            # Check if this is an Ollama provider or API URL for streaming
            is_ollama_api = (profile.provider == "ollama" or 
                            "ollama" in profile.url.lower() or 
                            profile.url.endswith("/api/generate"))
            
            # Handle streaming response if requested and supported
            if stream and is_ollama_api:
                return await self._handle_streaming_response(
                    chat_id=chat_id,
                    profile=profile,
                    previous_messages=previous_messages,
                    request_id=request_id
                )
            
            # Get response from the model (non-streaming)
            return await self._handle_non_streaming_response(
                chat_id=chat_id,
                profile=profile,
                previous_messages=previous_messages,
                request_id=request_id
            )
                
        except (ChatNotFoundError, ProfileNotFoundError, ModelAPIException):
            # These exceptions are already properly formatted, just re-raise them
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error processing message: {str(e)}",
                extra={"request_id": request_id},
                exc_info=True
            )
            raise MessageCreationError(
                "Failed to process message due to database error",
                original_exception=e
            )
        except Exception as e:
            # Catch any other unexpected exceptions
            error_message = f"Unexpected error processing message: {str(e)}"
            logger.error(
                error_message,
                extra={"request_id": request_id},
                exc_info=True
            )
            raise MessageCreationError(error_message, original_exception=e)

    async def _handle_streaming_response(
        self,
        chat_id: int,
        profile: ProfileModel,
        previous_messages: List[MessageModel],
        request_id: str
    ):
        """
        Handle streaming response from the model API.
        
        Args:
            chat_id: The ID of the chat.
            profile: The profile with model configuration.
            previous_messages: List of previous messages for context.
            request_id: Request ID for logging.
            
        Returns:
            StreamingResponse object for FastAPI.
            
        Raises:
            ModelAPIException: If there's an error communicating with the model API.
        """
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
            response_generator = stream_model_response(
                url=profile.url,
                model_name=profile.model_name,
                messages=previous_messages,
                token_size=profile.token_size,
                provider=profile.provider or "ollama"
            )
            
            # Create a background task to save the complete response
            async def save_complete_response():
                try:
                    full_response = ""
                    async for chunk in stream_model_response(
                        url=profile.url,
                        model_name=profile.model_name,
                        messages=previous_messages,
                        token_size=profile.token_size,
                        provider=profile.provider or "custom",  # Pass provider info
                        stream=False  # Get the full response in one go
                    ):
                        full_response += chunk
                    
                    # Create a new session for the background task
                    # to avoid session conflicts
                    bg_db = SessionLocal()
                    try:
                        # Update the message with the complete response
                        db_message = bg_db.query(MessageModel).filter(
                            MessageModel.id == assistant_message.id
                        ).first()
                        
                        if db_message and full_response.strip():
                            db_message.content = full_response
                            bg_db.commit()
                            
                            logger.info(
                                f"Updated assistant message (ID: {assistant_message.id}) with complete response",
                                extra={
                                    "request_id": request_id,
                                    "message_id": assistant_message.id,
                                    "content_length": len(full_response)
                                }
                            )
                        else:
                            logger.warning(
                                f"Could not update assistant message (ID: {assistant_message.id}) - "
                                f"Message not found or empty response",
                                extra={
                                    "request_id": request_id,
                                    "message_id": assistant_message.id,
                                    "found": db_message is not None,
                                    "response_length": len(full_response) if full_response else 0
                                }
                            )
                    except Exception as e:
                        logger.error(
                            f"Error saving complete response for message {assistant_message.id}: {str(e)}",
                            extra={"request_id": request_id},
                            exc_info=True
                        )
                    finally:
                        bg_db.close()
                except Exception as e:
                    logger.error(
                        f"Error in background task for message {assistant_message.id}: {str(e)}",
                        extra={"request_id": request_id},
                        exc_info=True
                    )
            
            # Start the background task
            asyncio.create_task(save_complete_response())
            
            # Return the streaming response
            return create_streaming_response(response_generator)
            
        except Exception as e:
            logger.error(
                f"Error setting up streaming response: {str(e)}",
                extra={"request_id": request_id},
                exc_info=True
            )
            # Fall back to non-streaming response
            return await self._handle_non_streaming_response(
                chat_id=chat_id,
                profile=profile,
                previous_messages=previous_messages,
                request_id=request_id
            )

    async def _handle_non_streaming_response(
        self,
        chat_id: int,
        profile: ProfileModel,
        previous_messages: List[MessageModel],
        request_id: str
    ) -> MessageModel:
        """
        Handle non-streaming response from the model API.
        
        Args:
            chat_id: The ID of the chat.
            profile: The profile with model configuration.
            previous_messages: List of previous messages for context.
            request_id: Request ID for logging.
            
        Returns:
            The newly created assistant MessageModel object.
            
        Raises:
            ModelAPIException: If there's an error communicating with the model API.
        """
        try:
            # Get response from the model
            response_text = await self.model_service.get_model_response(
                url=profile.url,
                model_name=profile.model_name,
                messages=previous_messages,
                token_size=profile.token_size,
                provider=profile.provider or "custom"  # Pass provider info
            )
            
            # Create assistant message
            return self.create_assistant_message(chat_id, response_text, request_id)
            
        except ModelAPIException:
            # This exception already has detailed error info and has been logged
            # Just pass it through to be handled by the exception handler
            raise
            
        except Exception as e:
            # Unexpected exception not handled by our ModelAPIException
            error_message = f"Unexpected error communicating with model API: {str(e)}"
            logger.error(
                error_message,
                extra={"request_id": request_id},
                exc_info=True
            )
            raise ModelAPIException(
                detail=error_message,
                original_exception=e
            )

    def create_assistant_message(
        self, 
        chat_id: int, 
        content: str,
        request_id: str = None
    ) -> MessageModel:
        """
        Creates a new assistant message in a chat.

        Args:
            chat_id: The ID of the chat to create the message in.
            content: The content of the assistant message.
            request_id: Optional request ID for logging.

        Returns:
            The newly created MessageModel object.

        Raises:
            MessageCreationError: If the message cannot be created due to a database error.
        """
        if request_id is None:
            request_id = str(uuid.uuid4())
            
        try:
            # Create and save assistant message
            assistant_message = MessageModel(
                chat_id=chat_id,
                role="assistant",
                content=content
            )
            self.db.add(assistant_message)
            self.db.commit()
            self.db.refresh(assistant_message)
            
            logger.info(
                f"Saved assistant response (ID: {assistant_message.id}) in chat {chat_id}",
                extra={
                    "request_id": request_id,
                    "message_id": assistant_message.id,
                    "content_length": len(content)
                }
            )
            
            return assistant_message
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(
                f"Database error creating assistant message: {str(e)}",
                extra={"request_id": request_id},
                exc_info=True
            )
            raise MessageCreationError(
                "Failed to create assistant message due to database error",
                original_exception=e
            )
