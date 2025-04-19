import logging
from typing import List, Optional

from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Import the actual SQLAlchemy models
from localchat.models import ChatModel, ChatCreate
# Import Pydantic schemas from schemas module
from localchat.utils import get_db_dependency
from localchat.exceptions import (
    ChatNotFoundError,
    ChatCreationError,
    ChatDeletionError,
    ProfileNotFoundError,
    DatabaseOperationError
)
from localchat.services.profile_service import ProfileService

logger = logging.getLogger(__name__)


class ChatService:
    """Service layer for chat session operations."""

    def __init__(
        self,
        db: Session = Depends(get_db_dependency),
        profile_service: ProfileService = Depends(ProfileService)
    ):
        """
        Initializes the ChatService with database and profile service dependencies.

        Args:
            db: The SQLAlchemy Session object injected by FastAPI.
            profile_service: The ProfileService instance injected by FastAPI.
        """
        self.db = db
        self.profile_service = profile_service
    def create_chat(self, chat_data: ChatCreate) -> ChatModel:
        """
        Creates a new chat session.

        Args:
            chat_data: The data for the new chat.

        Returns:
            The newly created ChatModel object.

        Raises:
            ChatCreationError: If the profile ID is invalid or a database error occurs.
        """
        logger.info(f"Attempting to create chat: {chat_data.title} for profile {chat_data.profile_id}")
        # Validate profile exists using injected service
        try:
            self.profile_service.get_profile(chat_data.profile_id)
            logger.debug(f"Profile {chat_data.profile_id} validated successfully for new chat.")
        except ProfileNotFoundError as e:
            logger.error(f"Cannot create chat: Profile {chat_data.profile_id} not found.", exc_info=False)
            # Raise ChatCreationError indicating precondition failure
            raise ChatCreationError(f"Cannot create chat: Profile {chat_data.profile_id} not found", is_client_error=True) from e
        except DatabaseOperationError as e:
            logger.error(f"Cannot create chat due to DB error validating profile {chat_data.profile_id}: {e}", exc_info=True)
            raise ChatCreationError(f"Cannot create chat due to DB error validating profile {chat_data.profile_id}") from e

        # Proceed with chat creation
        db_chat = ChatModel(**chat_data.dict())
        try:
            self.db.add(db_chat)
            self.db.commit()
            self.db.refresh(db_chat)
            logger.info(f"Successfully created chat: {db_chat.title} (ID: {db_chat.id})")
            return db_chat
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error creating chat '{chat_data.title}': {e}", exc_info=True)
            raise ChatCreationError(f"Database error creating chat '{chat_data.title}'", original_exception=e)

    def get_chat(self, chat_id: int) -> ChatModel:
        """
        Retrieves a single chat session by its ID.

        Args:
            chat_id: The ID of the chat to retrieve.

        Returns:
            The ChatModel object.

        Raises:
            ChatNotFoundError: If the chat with the given ID does not exist.
            DatabaseOperationError: If a database error occurs during retrieval.
        """
        logger.debug(f"Attempting to retrieve chat with id: {chat_id}")
        try:
            chat = self.db.query(ChatModel).filter(ChatModel.id == chat_id).first()
            if not chat:
                logger.warning(f"Chat not found with id: {chat_id}")
                raise ChatNotFoundError(f"Chat with id {chat_id} not found")
            logger.debug(f"Successfully retrieved chat: {chat.title} (ID: {chat_id})")
            return chat
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving chat {chat_id}: {e}", exc_info=True)
            raise DatabaseOperationError(f"Database error retrieving chat {chat_id}", original_exception=e)

    def get_chats(self, profile_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[ChatModel]:
        """
        Retrieves a list of chat sessions with pagination, optionally filtered by profile.

        Args:
            profile_id: Optional ID of the profile to filter chats by.
            skip: Number of chats to skip.
            limit: Maximum number of chats to return.

        Returns:
            A list of ChatModel objects.

        Raises:
            DatabaseOperationError: If a database error occurs during retrieval.
        """
        logger.debug(f"Attempting to retrieve chats" + (f" for profile {profile_id}" if profile_id else "") + f" (skip={skip}, limit={limit})")
        try:
            query = self.db.query(ChatModel)
            if profile_id is not None:
                query = query.filter(ChatModel.profile_id == profile_id)
            chats = query.offset(skip).limit(limit).all()
            logger.debug(f"Successfully retrieved {len(chats)} chats")
            return chats
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving chats: {e}", exc_info=True)
            raise DatabaseOperationError("Database error retrieving chats", original_exception=e)

    def delete_chat(self, chat_id: int) -> None:
        """
        Deletes a chat session.

        Args:
            chat_id: The ID of the chat to delete.

        Raises:
            ChatNotFoundError: If the chat with the given ID does not exist.
            ChatDeletionError: If the chat cannot be deleted due to a database error.
        """
        logger.info(f"Attempting to delete chat with id: {chat_id}")
        db_chat = self.get_chat(chat_id)  # This will raise ChatNotFoundError if not found

        try:
            self.db.delete(db_chat)
            self.db.commit()
            logger.info(f"Successfully deleted chat: {db_chat.title} (ID: {chat_id})")
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error deleting chat {chat_id}: {e}", exc_info=True)
            raise ChatDeletionError(f"Database error deleting chat {chat_id}", original_exception=e)
            
    # def update_chat(self, chat_id: int, chat_data: ChatUpdate) -> ChatModel:
    #     """
    #     Updates an existing chat session.

    #     Args:
    #         chat_id: The ID of the chat to update.
    #         chat_data: The updated data for the chat.

    #     Returns:
    #         The updated ChatModel object.

    #     Raises:
    #         ChatNotFoundError: If the chat with the given ID does not exist.
    #         ChatUpdateError: If the chat cannot be updated due to a database error.
    #     """
    #     logger.info(f"Attempting to update chat with id: {chat_id}")
    #     db_chat = self.get_chat(chat_id)  # This will raise ChatNotFoundError if not found

    #     update_data = chat_data.dict(exclude_unset=True)
    #     if not update_data:
    #         logger.warning(f"Update called for chat {chat_id} with no data to update.")
    #         return db_chat  # No changes to make

    #     logger.debug(f"Updating chat {chat_id} with data: {update_data}")
    #     for key, value in update_data.items():
    #         setattr(db_chat, key, value)

    #     try:
    #         self.db.add(db_chat)
    #         self.db.commit()
    #         self.db.refresh(db_chat)
    #         logger.info(f"Successfully updated chat: {db_chat.title} (ID: {chat_id})")
    #         return db_chat
    #     except SQLAlchemyError as e:
    #         self.db.rollback()
    #         logger.error(f"Database error updating chat {chat_id}: {e}", exc_info=True)
    #         raise ChatUpdateError(f"Database error updating chat {chat_id}", original_exception=e)
