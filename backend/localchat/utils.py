from typing import Dict, Any, Optional

from sqlalchemy.exc import SQLAlchemyError
from .models import  SessionLocal
from .error_handlers import  DatabaseException
import logging

# Get logger
logger = logging.getLogger("localchat")

def get_db_dependency():
    """
    Create a database session dependency for FastAPI.
    Includes error handling for database operations.
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Database error: {str(e)}", exc_info=True)
        raise DatabaseException(
            detail="Database operation failed",
            original_exception=e
        )
    finally:
        db.close()


def extract_response_text(response_data: Dict[str, Any]) -> Optional[str]:
    """
    Extract the response text from various API response formats.

    Args:
        response_data: The JSON response data from the model API

    Returns:
        The extracted response text, or None if no text could be extracted
    """
    # OpenAI-like format
    if "choices" in response_data and len(response_data["choices"]) > 0:
        choice = response_data["choices"][0]
        if isinstance(choice, dict):
            if "message" in choice and "content" in choice["message"]:
                return choice["message"]["content"]
            elif "text" in choice:
                return choice["text"]

    # Ollama format
    if "response" in response_data:
        return response_data["response"]

    # Hugging Face format
    if "generated_text" in response_data:
        return response_data["generated_text"]

    # Anthropic format (older API)
    if "completion" in response_data:
        return response_data["completion"]

    # Anthropic Claude API
    if "content" in response_data and isinstance(response_data["content"], list):
        for content_block in response_data["content"]:
            if isinstance(content_block, dict) and content_block.get("type") == "text":
                return content_block.get("text", "")

    # Cohere format
    if "generations" in response_data and len(response_data["generations"]) > 0:
        generation = response_data["generations"][0]
        if isinstance(generation, dict) and "text" in generation:
            return generation["text"]

    # AI21 format
    if "completions" in response_data and len(response_data["completions"]) > 0:
        completion = response_data["completions"][0]
        if isinstance(completion, dict) and "data" in completion and "text" in completion["data"]:
            return completion["data"]["text"]

    # If we can't determine the format, return the raw response as a string
    if isinstance(response_data, dict):
        return str(response_data)

    return None
