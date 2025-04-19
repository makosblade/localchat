import logging
from typing import List

from fastapi import Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Import the actual SQLAlchemy model, not the Pydantic schema
from localchat.models import ProfileModel, ProfileCreate
from localchat.utils import get_db_dependency
from localchat.exceptions import (
    ProfileNotFoundError,
    ProfileCreationError,
    ProfileUpdateError,
    ProfileDeletionError,
    DatabaseOperationError
)

logger = logging.getLogger(__name__)


# ProfileUpdate is now imported from schemas


class ProfileService:
    """
    Service for profile (model/user config) CRUD and validation.
    """
    def __init__(self, db: Session = Depends(get_db_dependency)):
        self.db = db

    def create_profile(self, profile_data: ProfileCreate) -> ProfileModel:
        """
        Creates a new profile.

        Args:
            profile_data: The data for the new profile.

        Returns:
            The newly created ProfileModel object.

        Raises:
            ProfileCreationError: If the profile cannot be created due to a database error.
        """
        logger.info(f"Attempting to create profile: {profile_data.name}")
        db_profile = ProfileModel(**profile_data.dict())
        try:
            self.db.add(db_profile)
            self.db.commit()
            self.db.refresh(db_profile)
            logger.info(f"Successfully created profile: {db_profile.name} (ID: {db_profile.id})")
            return db_profile
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error creating profile '{profile_data.name}': {e}", exc_info=True)
            raise ProfileCreationError(f"Database error creating profile '{profile_data.name}'", original_exception=e)

    def get_profile(self, profile_id: int) -> ProfileModel:
        """
        Retrieves a single profile by its ID.

        Args:
            profile_id: The ID of the profile to retrieve.

        Returns:
            The ProfileModel object.

        Raises:
            ProfileNotFoundError: If the profile with the given ID does not exist.
            DatabaseOperationError: If a database error occurs during retrieval.
        """
        logger.debug(f"Attempting to retrieve profile with id: {profile_id}")
        try:
            profile = self.db.query(ProfileModel).filter(ProfileModel.id == profile_id).first()
            if not profile:
                logger.warning(f"Profile not found with id: {profile_id}")
                raise ProfileNotFoundError(f"Profile with id {profile_id} not found")
            logger.debug(f"Successfully retrieved profile: {profile.name} (ID: {profile_id})")
            return profile
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving profile {profile_id}: {e}", exc_info=True)
            raise DatabaseOperationError(f"Database error retrieving profile {profile_id}", original_exception=e)

    def get_profiles(self, skip: int = 0, limit: int = 100) -> List[ProfileModel]:
        """
        Retrieves a list of profiles with pagination.

        Args:
            skip: Number of profiles to skip.
            limit: Maximum number of profiles to return.

        Returns:
            A list of ProfileModel objects.

        Raises:
            DatabaseOperationError: If a database error occurs during retrieval.
        """
        logger.debug(f"Attempting to retrieve profiles (skip={skip}, limit={limit})")
        try:
            profiles = self.db.query(ProfileModel).offset(skip).limit(limit).all()
            logger.debug(f"Successfully retrieved {len(profiles)} profiles")
            return profiles
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving profiles: {e}", exc_info=True)
            raise DatabaseOperationError("Database error retrieving profiles", original_exception=e)

    def update_profile(self, profile_id: int, profile_data: ProfileCreate) -> ProfileModel:
        """
        Updates an existing profile.

        Args:
            profile_id: The ID of the profile to update.
            profile_data: The updated data for the profile.

        Returns:
            The updated ProfileModel object.

        Raises:
            ProfileNotFoundError: If the profile with the given ID does not exist.
            ProfileUpdateError: If the profile cannot be updated due to a database error.
        """
        logger.info(f"Attempting to update profile with id: {profile_id}")
        db_profile = self.get_profile(profile_id)  # This will raise ProfileNotFoundError if not found

        update_data = profile_data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_profile, key, value)

        try:
            self.db.add(db_profile)
            self.db.commit()
            self.db.refresh(db_profile)
            logger.info(f"Successfully updated profile: {db_profile.name} (ID: {profile_id})")
            return db_profile
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error updating profile {profile_id}: {e}", exc_info=True)
            raise ProfileUpdateError(f"Database error updating profile {profile_id}", original_exception=e)

    def delete_profile(self, profile_id: int) -> None:
        """
        Deletes a profile.

        Args:
            profile_id: The ID of the profile to delete.

        Raises:
            ProfileNotFoundError: If the profile with the given ID does not exist.
            ProfileDeletionError: If the profile cannot be deleted due to a database error.
        """
        logger.info(f"Attempting to delete profile with id: {profile_id}")
        db_profile = self.get_profile(profile_id)  # This will raise ProfileNotFoundError if not found

        try:
            self.db.delete(db_profile)
            self.db.commit()
            logger.info(f"Successfully deleted profile: {db_profile.name} (ID: {profile_id})")
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Database error deleting profile {profile_id}: {e}", exc_info=True)
            raise ProfileDeletionError(f"Database error deleting profile {profile_id}", original_exception=e)
