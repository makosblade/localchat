from typing import List, Optional, Dict, Any
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, BackgroundTasks

from .models import (
    Profile, ProfileCreate,
    Chat, ChatCreate,
    Message, MessageCreate,
)
from .error_handlers import ModelAPIException, DatabaseException
from .exceptions import (
    # Profile exceptions
    ProfileNotFoundError, ProfileCreationError, ProfileUpdateError, ProfileDeletionError,
    # Chat exceptions
    ChatNotFoundError, ChatCreationError, ChatUpdateError, ChatDeletionError,
    # Message exceptions
    MessageCreationError, MessageFetchError, MessageUpdateError,
    # Model/Provider exceptions
    ModelInteractionError, ProviderConfigurationError, ModelNotFoundError,
    # Generic exceptions
    DatabaseOperationError
)
from .services.profile_service import ProfileService
from .services.chat_service import ChatService
from .services.message_service import MessageService
from .services.provider_service import ProviderService

from .utils import get_db_dependency

# Get logger
logger = logging.getLogger("localchat")

router = APIRouter()

# Dependency to get the database session
get_db = get_db_dependency

# Provider endpoints
@router.get("/models/ollama", response_model=List[Dict[str, Any]])
async def get_ollama_available_models(
    request: Request, 
    base_url: Optional[str] = None,
    profile_id: Optional[int] = None,
    provider_service: ProviderService = Depends(ProviderService)
):
    """
    Get a list of available models from Ollama.
    
    Args:
        base_url: Optional base URL for the Ollama API. Overrides profile settings if provided.
        profile_id: Optional profile ID to use for provider configuration.
        
    Returns:
        List of model information dictionaries
    """
    request_id = str(uuid.uuid4())
    logger.info(
        f"Fetching available Ollama models", 
        extra={
            "request_id": request_id,
            "client_ip": request.client.host,
            "base_url": base_url or "from_profile" if profile_id else "default",
            "profile_id": profile_id
        }
    )
    
    try:
        models = await provider_service.list_models("ollama", profile_id, base_url)
        return models
    except ProviderConfigurationError as e:
        logger.error(
            f"Provider configuration error: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=400 if e.is_client_error else 500,
            detail=str(e)
        )
    except ModelInteractionError as e:
        logger.error(
            f"Error communicating with model provider: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(
            f"Unexpected error fetching Ollama models: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(status_code=500, detail="Internal server error")

# Profile endpoints
@router.post("/profiles/", response_model=Profile, status_code=201)
def create_profile(profile: ProfileCreate, request: Request, profile_service: ProfileService = Depends(ProfileService)):
    request_id = str(uuid.uuid4())
    logger.info(
        f"Creating new profile: {profile.name}", 
        extra={
            "request_id": request_id,
            "client_ip": request.client.host,
            "profile_name": profile.name
        }
    )
    
    try:
        db_profile = profile_service.create_profile(profile)
        logger.info(
            f"Successfully created profile: {profile.name} (ID: {db_profile.id})",
            extra={"request_id": request_id, "profile_id": db_profile.id}
        )
        return db_profile
    except ProfileCreationError as e:
        logger.error(
            f"Error creating profile: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise HTTPException(
            status_code=400 if e.is_client_error else 500,
            detail=str(e)
        )
    except DatabaseOperationError as e:
        logger.error(
            f"Database error creating profile: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise DatabaseException(
            detail="Failed to create profile due to database error",
            original_exception=e.original_exception
        )

@router.get("/profiles/", response_model=List[Profile])
def read_profiles(request: Request, skip: int = 0, limit: int = 100, profile_service: ProfileService = Depends(ProfileService)):
    request_id = str(uuid.uuid4())
    logger.info(
        f"Fetching profiles (skip={skip}, limit={limit})",
        extra={
            "request_id": request_id,
            "client_ip": request.client.host,
            "skip": skip,
            "limit": limit
        }
    )
    
    try:
        profiles = profile_service.get_profiles(skip, limit)
        logger.info(
            f"Successfully fetched {len(profiles)} profiles",
            extra={"request_id": request_id, "count": len(profiles)}
        )
        return profiles
    except DatabaseOperationError as e:
        logger.error(
            f"Database error fetching profiles: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise DatabaseException(
            detail="Failed to fetch profiles due to database error",
            original_exception=e.original_exception
        )

@router.get("/profiles/{profile_id}", response_model=Profile)
def read_profile(profile_id: int, profile_service: ProfileService = Depends(ProfileService)):
    try:
        db_profile = profile_service.get_profile(profile_id)
        return db_profile
    except ProfileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DatabaseOperationError as e:
        logger.error(f"Database error retrieving profile {profile_id}: {e}", exc_info=True)
        raise DatabaseException(
            detail=f"Failed to retrieve profile {profile_id} due to database error",
            original_exception=e.original_exception
        )

@router.put("/profiles/{profile_id}", response_model=Profile)
def update_profile(profile_id: int, profile: ProfileCreate, profile_service: ProfileService = Depends(ProfileService)):
    try:
        db_profile = profile_service.update_profile(profile_id, profile)
        return db_profile
    except ProfileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ProfileUpdateError as e:
        logger.error(f"Error updating profile {profile_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=400 if e.is_client_error else 500,
            detail=str(e)
        )
    except DatabaseOperationError as e:
        logger.error(f"Database error updating profile {profile_id}: {e}", exc_info=True)
        raise DatabaseException(
            detail=f"Failed to update profile {profile_id} due to database error",
            original_exception=e.original_exception
        )

@router.delete("/profiles/{profile_id}", response_model=Dict[str, str])
def delete_profile(profile_id: int, profile_service: ProfileService = Depends(ProfileService)):
    try:
        profile_service.delete_profile(profile_id)
        return {"detail": "Profile deleted successfully"}
    except ProfileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ProfileDeletionError as e:
        logger.error(f"Error deleting profile {profile_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=400 if e.is_client_error else 500,
            detail=str(e)
        )
    except DatabaseOperationError as e:
        logger.error(f"Database error deleting profile {profile_id}: {e}", exc_info=True)
        raise DatabaseException(
            detail=f"Failed to delete profile {profile_id} due to database error",
            original_exception=e.original_exception
        )

# Chat endpoints
@router.post("/chats/", response_model=Chat, status_code=201)
def create_chat(chat: ChatCreate, chat_service: ChatService = Depends(ChatService)):
    try:
        db_chat = chat_service.create_chat(chat)
        return db_chat
    except ChatCreationError as e:
        logger.error(f"Error creating chat: {e}", exc_info=True)
        raise HTTPException(
            status_code=400 if e.is_client_error else 500,
            detail=str(e)
        )
    except DatabaseOperationError as e:
        logger.error(f"Database error creating chat: {e}", exc_info=True)
        raise DatabaseException(
            detail="Failed to create chat due to database error",
            original_exception=e.original_exception
        )

@router.get("/chats/", response_model=List[Chat])
def read_chats(
    profile_id: Optional[int] = Query(None, description="Filter chats by profile ID"),
    skip: int = 0, 
    limit: int = 100, 
    chat_service: ChatService = Depends(ChatService)
):
    try:
        chats = chat_service.get_chats(profile_id, skip, limit)
        return chats
    except DatabaseOperationError as e:
        logger.error(f"Database error retrieving chats: {e}", exc_info=True)
        raise DatabaseException(
            detail="Failed to retrieve chats due to database error",
            original_exception=e.original_exception
        )

@router.get("/chats/{chat_id}", response_model=Chat)
def read_chat(chat_id: int, chat_service: ChatService = Depends(ChatService)):
    try:
        db_chat = chat_service.get_chat(chat_id)
        return db_chat
    except ChatNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DatabaseOperationError as e:
        logger.error(f"Database error retrieving chat {chat_id}: {e}", exc_info=True)
        raise DatabaseException(
            detail=f"Failed to retrieve chat {chat_id} due to database error",
            original_exception=e.original_exception
        )

@router.delete("/chats/{chat_id}", response_model=Dict[str, str])
def delete_chat(chat_id: int, chat_service: ChatService = Depends(ChatService)):
    try:
        chat_service.delete_chat(chat_id)
        return {"detail": "Chat deleted successfully"}
    except ChatNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ChatDeletionError as e:
        logger.error(f"Error deleting chat {chat_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=400 if e.is_client_error else 500,
            detail=str(e)
        )
    except DatabaseOperationError as e:
        logger.error(f"Database error deleting chat {chat_id}: {e}", exc_info=True)
        raise DatabaseException(
            detail=f"Failed to delete chat {chat_id} due to database error",
            original_exception=e.original_exception
        )

# Message endpoints
@router.get("/chats/{chat_id}/messages/", response_model=List[Message])
def read_messages(
    chat_id: int, 
    request: Request,
    skip: int = 0, 
    limit: int = 100, 
    message_service: MessageService = Depends(MessageService)
):
    request_id = str(uuid.uuid4())
    logger.info(
        f"Fetching messages for chat ID: {chat_id}",
        extra={
            "request_id": request_id,
            "client_ip": request.client.host,
            "chat_id": chat_id,
            "skip": skip,
            "limit": limit
        }
    )
    
    try:
        # Use the message service to get messages
        messages = message_service.get_messages(chat_id, skip, limit, request_id)
        
        logger.info(
            f"Successfully fetched {len(messages)} messages for chat ID: {chat_id}",
            extra={"request_id": request_id, "count": len(messages)}
        )
        
        return messages
    except ChatNotFoundError as e:
        logger.warning(
            f"Attempted to fetch messages for non-existent chat: {chat_id}",
            extra={"request_id": request_id}
        )
        raise HTTPException(status_code=404, detail=str(e))
    except MessageFetchError as e:
        logger.error(
            f"Error fetching messages: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise DatabaseException(
            detail="Failed to fetch messages due to database error",
            original_exception=e.original_exception if hasattr(e, 'original_exception') else None
        )

@router.post("/chats/{chat_id}/messages/", response_model=Message)
async def create_message(
    chat_id: int, 
    message: MessageCreate, 
    request: Request,
    stream: bool = Query(False, description="Whether to stream the response"),
    message_service: MessageService = Depends(MessageService)
):
    request_id = str(uuid.uuid4())
    logger.info(
        f"Creating new message in chat ID: {chat_id}",
        extra={
            "request_id": request_id,
            "client_ip": request.client.host,
            "chat_id": chat_id,
            "message_role": message.role,
            "content_length": len(message.content),
            "stream": stream
        }
    )
    
    try:
        # Use the message service to create the message and get AI response
        response = await message_service.create_message(chat_id, message, stream, request_id)
        return response
        
    except ChatNotFoundError as e:
        logger.warning(
            f"Attempted to create message in non-existent chat: {chat_id}",
            extra={"request_id": request_id}
        )
        raise HTTPException(status_code=404, detail=str(e))
        
    except ProfileNotFoundError as e:
        logger.error(
            f"Profile not found for chat {chat_id}",
            extra={"request_id": request_id}
        )
        raise HTTPException(status_code=404, detail=str(e))
        
    except MessageCreationError as e:
        logger.error(
            f"Error creating message: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise DatabaseException(
            detail="Failed to create message due to database error",
            original_exception=e.original_exception if hasattr(e, 'original_exception') else None
        )
        
    except ModelAPIException as e:
        # This exception already has detailed error info and has been logged
        # Just pass it through to be handled by the exception handler
        raise
