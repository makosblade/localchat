from typing import Any, Optional

class LocalChatException(Exception):
    """Base exception for LocalChat application errors."""
    def __init__(self, detail: str, original_exception: Optional[Exception] = None, is_client_error: bool = False):
        self.detail = detail
        self.original_exception = original_exception
        self.is_client_error = is_client_error # Flag to suggest 4xx vs 5xx status
        super().__init__(detail)

    def __str__(self) -> str:
        if self.original_exception:
            return f"{self.detail} (Original exception: {self.original_exception})"
        return self.detail

# --- Database Related Exceptions ---
class DatabaseOperationError(LocalChatException):
    """Raised when a generic database operation fails."""
    pass

# --- Profile Related Exceptions ---
class ProfileException(LocalChatException):
    """Base exception for profile-related errors."""
    pass

class ProfileNotFoundError(ProfileException):
    """Raised when a specific profile cannot be found."""
    def __init__(self, detail: str = "Profile not found", original_exception: Optional[Exception] = None):
        super().__init__(detail, original_exception, is_client_error=True) # Not found is client-addressable

class ProfileCreationError(ProfileException):
    """Raised when creating a profile fails."""
    pass

class ProfileUpdateError(ProfileException):
    """Raised when updating a profile fails."""
    pass

class ProfileDeletionError(ProfileException):
    """Raised when deleting a profile fails."""
    pass

# --- Chat Related Exceptions ---
class ChatException(LocalChatException):
    """Base exception for chat-related errors."""
    pass

class ChatNotFoundError(ChatException):
    """Raised when a specific chat cannot be found."""
    def __init__(self, detail: str = "Chat not found", original_exception: Optional[Exception] = None):
        super().__init__(detail, original_exception, is_client_error=True)

class ChatCreationError(ChatException):
    """Raised when creating a chat fails."""
    pass

class ChatUpdateError(ChatException):
    """Raised when updating a chat fails."""
    pass

class ChatDeletionError(ChatException):
    """Raised when deleting a chat fails."""
    pass

# --- Message Related Exceptions ---
class MessageException(LocalChatException):
    """Base exception for message-related errors."""
    pass

class MessageCreationError(MessageException):
    """Raised when creating a message fails."""
    pass

class MessageFetchError(MessageException):
     """Raised when fetching messages fails."""
     pass

class MessageUpdateError(MessageException):
    """Raised when updating a message fails (e.g., saving streamed content)."""
    pass


# --- Model/Provider Related Exceptions ---
class ModelInteractionError(LocalChatException):
    """Raised during issues communicating with the AI model provider."""
    pass

class ProviderConfigurationError(LocalChatException):
    """Raised when provider configuration (URL, API key) is invalid or missing."""
    pass

class ModelNotFoundError(ModelInteractionError):
    """Raised when the specified model is not available at the provider."""
    def __init__(self, detail: str = "Model not found at provider", original_exception: Optional[Exception] = None):
        super().__init__(detail, original_exception, is_client_error=True)
