import logging
from typing import List, Dict, Any, Optional

import httpx
from fastapi import Depends

from localchat.exceptions import (
    ProviderConfigurationError,
    ModelInteractionError,
    ProfileNotFoundError,
    DatabaseOperationError
)
from localchat.services.profile_service import ProfileService

logger = logging.getLogger(__name__)

# Define Base URL mapping (can be moved to config later)
PROVIDER_BASE_URLS = {
    "ollama": "/api/tags",
    # Add other providers if needed
}

class ProviderService:
    """Service layer for interacting with model providers (e.g., listing models)."""

    def __init__(
        self,
        profile_service: ProfileService = Depends(ProfileService)
    ):
        """
        Initializes the ProviderService with a profile service dependency.

        Args:
            profile_service: The ProfileService instance injected by FastAPI.
        """
        self.profile_service = profile_service

    async def list_models(self, provider: str, profile_id: Optional[int] = None, base_url_override: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lists available models from a specified provider.

        Args:
            provider: The name of the provider (e.g., 'ollama').
            profile_id: Optional ID of the profile to use for provider config (e.g., base URL).
            base_url_override: Optional explicit base URL to use, bypassing profile lookup.

        Returns:
            A list of dictionaries, each representing a model.

        Raises:
            ProviderConfigurationError: If the provider is unsupported or config is missing/invalid.
            ModelInteractionError: If communication with the provider fails.
        """
        logger.info(f"Attempting to list models for provider: {provider}")

        # Determine the base URL to use
        if base_url_override:
            base_url = base_url_override
            logger.debug(f"Using provided base URL override: {base_url}")
        elif profile_id is not None:
            try:
                profile = self.profile_service.get_profile(profile_id)
                # Assuming profile model has ollama_base_url, openai_api_key etc.
                base_url = getattr(profile, f"{provider}_base_url", None)
                if not base_url:
                    logger.error(f"Base URL for provider '{provider}' not found in profile {profile_id}")
                    raise ProviderConfigurationError(f"Base URL for provider '{provider}' not configured in profile {profile_id}")
                logger.debug(f"Using base URL from profile {profile_id}: {base_url}")
            except (ProfileNotFoundError, DatabaseOperationError) as e:
                logger.error(f"Error fetching profile {profile_id} to get base URL for provider {provider}: {e}")
                raise ProviderConfigurationError(f"Could not retrieve configuration for provider '{provider}' from profile {profile_id}") from e
        else:
            # Default fallback for Ollama only
            if provider.lower() == "ollama":
                base_url = "http://localhost:11434"
                logger.debug(f"Using default base URL for Ollama: {base_url}")
            else:
                logger.error(f"Cannot list models for '{provider}': Profile ID or base_url_override required.")
                raise ProviderConfigurationError(f"Configuration missing for provider '{provider}'. Provide profile_id or base_url_override.", is_client_error=True)

        # Validate provider and construct URL
        endpoint_path = PROVIDER_BASE_URLS.get(provider.lower())
        if not endpoint_path:
            logger.error(f"Unsupported provider specified: {provider}")
            raise ProviderConfigurationError(f"Unsupported provider: {provider}", is_client_error=True)

        # Clean up base URL
        if base_url.endswith("/"):
            base_url = base_url[:-1]
        if provider.lower() == "ollama" and base_url.endswith('/api/generate'):
            base_url = base_url.replace('/api/generate', '')

        # Construct full URL
        url = f"{base_url}{endpoint_path}"
        logger.debug(f"Requesting models from URL: {url}")

        # Make the API request
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()

                # Parse response based on provider
                if provider.lower() == "ollama":
                    models = data.get("models", [])
                    logger.info(f"Successfully listed {len(models)} models from Ollama at {base_url}")
                    return models
                else:
                    logger.error(f"Parsing logic not implemented for provider: {provider}")
                    raise ProviderConfigurationError(f"Parsing not implemented for provider: {provider}")

        except httpx.RequestError as e:
            logger.error(f"HTTP request error listing models from {url}: {e}", exc_info=True)
            raise ModelInteractionError(f"Error communicating with provider {provider} at {url}", original_exception=e)
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP status error {e.response.status_code} listing models from {url}: {e.response.text}", exc_info=True)
            status = e.response.status_code
            if status == 404:
                raise ProviderConfigurationError(f"Model listing endpoint not found at {url} (404). Check base URL.", original_exception=e)
            elif status == 401:
                raise ProviderConfigurationError(f"Authentication failed for provider {provider} at {url} (401). Check API key.", original_exception=e)
            else:
                raise ModelInteractionError(f"Provider {provider} returned error {status} when listing models at {url}", original_exception=e)
        except Exception as e:
            logger.error(f"Unexpected error listing models from {url}: {e}", exc_info=True)
            raise ModelInteractionError(f"Unexpected error processing response from {provider} at {url}", original_exception=e)
