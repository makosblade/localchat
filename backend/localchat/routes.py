from typing import List, Optional, Dict, Any
import logging
import uuid
import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import httpx

from .models import (
    Profile, ProfileCreate, ProfileModel,
    Chat, ChatCreate, ChatModel,
    Message, MessageCreate, MessageModel
)
from .services import get_model_response, get_db_dependency
from .error_handlers import ModelAPIException, DatabaseException
from .streaming import stream_model_response, create_streaming_response
from .ollama import get_ollama_models

# Get logger
logger = logging.getLogger("localchat")

router = APIRouter()

# Dependency to get the database session
get_db = get_db_dependency

# Provider endpoints
@router.get("/providers/ollama/models", response_model=List[Dict[str, Any]])
async def get_ollama_available_models(request: Request, base_url: Optional[str] = None):
    """
    Get a list of available models from Ollama.
    
    Args:
        base_url: Optional base URL for the Ollama API. Defaults to http://localhost:11434.
        
    Returns:
        List of model information dictionaries
    """
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    
    logger.info(
        f"Fetching available Ollama models",
        extra={
            "request_id": request_id,
            "base_url": base_url
        }
    )
    
    try:
        # Get models from Ollama
        models = await get_ollama_models(base_url)
        
        # Return the models list
        return models
    except Exception as e:
        logger.error(
            f"Error fetching Ollama models: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise

# Profile endpoints
@router.post("/profiles/", response_model=Profile)
def create_profile(profile: ProfileCreate, request: Request, db: Session = Depends(get_db)):
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
        # Check if profile with the same name already exists
        existing_profile = db.query(ProfileModel).filter(ProfileModel.name == profile.name).first()
        if existing_profile:
            logger.warning(
                f"Attempted to create duplicate profile: {profile.name}",
                extra={"request_id": request_id}
            )
            raise HTTPException(
                status_code=400, 
                detail=f"Profile with name '{profile.name}' already exists"
            )
        
        # Create new profile
        db_profile = ProfileModel(**profile.dict())
        db.add(db_profile)
        db.commit()
        db.refresh(db_profile)
        
        logger.info(
            f"Successfully created profile: {profile.name} (ID: {db_profile.id})",
            extra={"request_id": request_id, "profile_id": db_profile.id}
        )
        
        return db_profile
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            f"Database error creating profile: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise DatabaseException(
            detail="Failed to create profile due to database error",
            original_exception=e
        )

@router.get("/profiles/", response_model=List[Profile])
def read_profiles(request: Request, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
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
        profiles = db.query(ProfileModel).offset(skip).limit(limit).all()
        logger.info(
            f"Successfully fetched {len(profiles)} profiles",
            extra={"request_id": request_id, "count": len(profiles)}
        )
        return profiles
    except SQLAlchemyError as e:
        logger.error(
            f"Database error fetching profiles: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise DatabaseException(
            detail="Failed to fetch profiles due to database error",
            original_exception=e
        )

@router.get("/profiles/{profile_id}", response_model=Profile)
def read_profile(profile_id: int, db: Session = Depends(get_db)):
    db_profile = db.query(ProfileModel).filter(ProfileModel.id == profile_id).first()
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return db_profile

@router.put("/profiles/{profile_id}", response_model=Profile)
def update_profile(profile_id: int, profile: ProfileCreate, db: Session = Depends(get_db)):
    db_profile = db.query(ProfileModel).filter(ProfileModel.id == profile_id).first()
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Update profile attributes
    for key, value in profile.dict().items():
        setattr(db_profile, key, value)
    
    db.commit()
    db.refresh(db_profile)
    return db_profile

@router.delete("/profiles/{profile_id}")
def delete_profile(profile_id: int, db: Session = Depends(get_db)):
    db_profile = db.query(ProfileModel).filter(ProfileModel.id == profile_id).first()
    if db_profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    db.delete(db_profile)
    db.commit()
    return {"ok": True}

# Chat endpoints
@router.post("/chats/", response_model=Chat)
def create_chat(chat: ChatCreate, db: Session = Depends(get_db)):
    # Verify that the profile exists
    profile = db.query(ProfileModel).filter(ProfileModel.id == chat.profile_id).first()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    db_chat = ChatModel(**chat.dict())
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)
    return db_chat

@router.get("/chats/", response_model=List[Chat])
def read_chats(
    profile_id: Optional[int] = Query(None, description="Filter chats by profile ID"),
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    query = db.query(ChatModel)
    if profile_id is not None:
        query = query.filter(ChatModel.profile_id == profile_id)
    
    chats = query.offset(skip).limit(limit).all()
    return chats

@router.get("/chats/{chat_id}", response_model=Chat)
def read_chat(chat_id: int, db: Session = Depends(get_db)):
    db_chat = db.query(ChatModel).filter(ChatModel.id == chat_id).first()
    if db_chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return db_chat

@router.delete("/chats/{chat_id}")
def delete_chat(chat_id: int, db: Session = Depends(get_db)):
    db_chat = db.query(ChatModel).filter(ChatModel.id == chat_id).first()
    if db_chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    db.delete(db_chat)
    db.commit()
    return {"ok": True}

# Message endpoints
@router.get("/chats/{chat_id}/messages/", response_model=List[Message])
def read_messages(
    chat_id: int, 
    request: Request,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
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
        # Verify chat exists
        chat = db.query(ChatModel).filter(ChatModel.id == chat_id).first()
        if not chat:
            logger.warning(
                f"Attempted to fetch messages for non-existent chat: {chat_id}",
                extra={"request_id": request_id}
            )
            raise HTTPException(status_code=404, detail=f"Chat with ID {chat_id} not found")
        
        messages = db.query(MessageModel).filter(
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
        raise DatabaseException(
            detail="Failed to fetch messages due to database error",
            original_exception=e
        )

@router.post("/chats/{chat_id}/messages/", response_model=Message)
async def create_message(
    chat_id: int, 
    message: MessageCreate, 
    request: Request,
    stream: bool = Query(False, description="Whether to stream the response"),
    db: Session = Depends(get_db)
):
    request_id = str(uuid.uuid4())
    logger.info(
        f"Creating new message in chat ID: {chat_id}",
        extra={
            "request_id": request_id,
            "client_ip": request.client.host,
            "chat_id": chat_id,
            "message_role": message.role,
            "content_length": len(message.content)
        }
    )
    
    try:
        # Verify that the chat exists
        chat = db.query(ChatModel).filter(ChatModel.id == chat_id).first()
        if not chat:
            logger.warning(
                f"Attempted to create message in non-existent chat: {chat_id}",
                extra={"request_id": request_id}
            )
            raise HTTPException(status_code=404, detail=f"Chat with ID {chat_id} not found")
        
        # Save user message
        db_message = MessageModel(**message.dict(), chat_id=chat_id)
        db.add(db_message)
        db.commit()
        db.refresh(db_message)
        
        logger.info(
            f"Saved user message (ID: {db_message.id}) in chat {chat_id}",
            extra={
                "request_id": request_id,
                "message_id": db_message.id
            }
        )
        
        # Get profile information
        profile = db.query(ProfileModel).filter(ProfileModel.id == chat.profile_id).first()
        if not profile:
            logger.error(
                f"Profile not found for chat {chat_id} (profile_id: {chat.profile_id})",
                extra={
                    "request_id": request_id,
                    "chat_id": chat_id,
                    "profile_id": chat.profile_id
                }
            )
            raise HTTPException(
                status_code=404, 
                detail=f"Profile with ID {chat.profile_id} not found for this chat"
            )
        
        # Get previous messages for context
        previous_messages = db.query(MessageModel).filter(
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
            try:
                # Create a new empty message to be filled with the streamed content
                assistant_message = MessageModel(
                    chat_id=chat_id,
                    role="assistant",
                    content=""  # Will be filled after streaming completes
                )
                db.add(assistant_message)
                db.commit()
                db.refresh(assistant_message)
                
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
                    
                    # Update the message with the complete response
                    db_message = db.query(MessageModel).filter(MessageModel.id == assistant_message.id).first()
                    if db_message:
                        db_message.content = full_response
                        db.commit()
                        
                        logger.info(
                            f"Updated assistant message (ID: {assistant_message.id}) with complete response",
                            extra={
                                "request_id": request_id,
                                "message_id": assistant_message.id,
                                "content_length": len(full_response)
                            }
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
                pass
        
        # Get response from the model (non-streaming)
        try:
            response_text = await get_model_response(
                url=profile.url,
                model_name=profile.model_name,
                messages=previous_messages,
                token_size=profile.token_size,
                provider=profile.provider or "custom"  # Pass provider info
            )
            
            # Save assistant message
            assistant_message = MessageModel(
                chat_id=chat_id,
                role="assistant",
                content=response_text
            )
            db.add(assistant_message)
            db.commit()
            db.refresh(assistant_message)
            
            logger.info(
                f"Saved assistant response (ID: {assistant_message.id}) in chat {chat_id}",
                extra={
                    "request_id": request_id,
                    "message_id": assistant_message.id,
                    "content_length": len(response_content)
                }
            )
            
            return assistant_message
            
        except ModelAPIException as e:
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
            
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            f"Database error processing message: {str(e)}",
            extra={"request_id": request_id},
            exc_info=True
        )
        raise DatabaseException(
            detail="Failed to process message due to database error",
            original_exception=e
        )
