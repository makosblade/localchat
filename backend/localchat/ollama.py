from typing import List, Dict, Any, Optional
import logging
import httpx
from fastapi import HTTPException

# Get logger
logger = logging.getLogger("localchat")

async def get_ollama_models(base_url: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch the list of available models from Ollama.
    
    Args:
        base_url: Optional base URL for the Ollama API. Defaults to http://localhost:11434.
        
    Returns:
        List of model information dictionaries
        
    Raises:
        HTTPException: If there's an error communicating with the Ollama API
    """
    # Use default Ollama URL if not provided
    if not base_url:
        base_url = "http://localhost:11434"
    
    # Remove trailing slash if present
    if base_url.endswith("/"):
        base_url = base_url[:-1]
    
    # Ensure we're using the base URL, not the generate endpoint
    if base_url.endswith('/api/generate'):
        base_url = base_url.replace('/api/generate', '')
    
    # Construct the tags endpoint URL
    tags_url = f"{base_url}/api/tags"
    
    logger.info(
        f"Fetching available models from Ollama at {tags_url}",
        extra={"base_url": base_url}
    )
    
    try:
        # Send the request to the Ollama API
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(tags_url)
            
            # Check if the request was successful
            response.raise_for_status()
            
            # Parse the response
            response_data = response.json()
            
            # Extract the models list
            models = response_data.get("models", [])
            
            logger.info(
                f"Successfully fetched {len(models)} models from Ollama",
                extra={"model_count": len(models)}
            )
            
            return models
                
    except httpx.HTTPStatusError as e:
        # Handle HTTP errors from the Ollama API
        error_message = f"Ollama API returned error status: {e.response.status_code}"
        
        try:
            error_data = e.response.json()
            error_detail = error_data.get("error", {}).get("message", str(e))
        except:
            error_detail = e.response.text[:500] if e.response.text else str(e)
        
        logger.error(
            f"HTTP error from Ollama API: {error_message}",
            extra={
                "status_code": e.response.status_code,
                "error_detail": error_detail
            }
        )
        
        raise HTTPException(
            status_code=502,
            detail=f"Error from Ollama API: {error_detail}"
        )
        
    except httpx.RequestError as e:
        # Handle network/connection errors
        error_message = f"Error connecting to Ollama API: {str(e)}"
        logger.error(error_message)
        
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to Ollama: {str(e)}"
        )
        
    except Exception as e:
        # Handle any other unexpected errors
        error_message = f"Unexpected error communicating with Ollama API: {str(e)}"
        logger.error(error_message, exc_info=True)
        
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching Ollama models: {str(e)}"
        )
