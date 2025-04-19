import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from localchat.services.interactions.interaction_service import ModelInteractionService
from localchat.services.interactions.streaming_strategy import StreamingInteractionStrategy
from localchat.services.interactions.non_streaming_strategy import NonStreamingInteractionStrategy
from localchat.services.adapters.base_adapter import ModelProviderAdapter
from localchat.models import MessageModel


@pytest.fixture
def mock_adapter():
    adapter = MagicMock(spec=ModelProviderAdapter)
    adapter.format_url.return_value = "http://test-url.com/api"
    adapter.format_request_payload.return_value = {"model": "test-model", "messages": []}
    adapter.extract_response_text.return_value = "Test response"
    adapter.extract_streaming_chunk.return_value = "Test chunk"
    adapter.is_final_chunk.return_value = False
    return adapter


@pytest.fixture
def mock_streaming_strategy():
    strategy = AsyncMock(spec=StreamingInteractionStrategy)
    
    async def mock_execute(*args, **kwargs):
        yield "Chunk 1"
        yield "Chunk 2"
        yield "Chunk 3"
    
    strategy.execute = mock_execute
    return strategy


@pytest.fixture
def mock_non_streaming_strategy():
    strategy = AsyncMock(spec=NonStreamingInteractionStrategy)
    strategy.execute.return_value = "Complete response"
    return strategy


@pytest.fixture
def interaction_service(mock_streaming_strategy, mock_non_streaming_strategy):
    return ModelInteractionService(
        streaming_strategy=mock_streaming_strategy,
        non_streaming_strategy=mock_non_streaming_strategy
    )


@pytest.mark.asyncio
async def test_execute_streaming(interaction_service):
    messages = [
        MessageModel(id=1, chat_id=1, role="user", content="Hello")
    ]
    
    chunks = []
    async for chunk in interaction_service.execute_streaming(
        url="http://test-url.com",
        model_name="test-model",
        messages=messages,
        provider="test-provider"
    ):
        chunks.append(chunk)
    
    assert chunks == ["Chunk 1", "Chunk 2", "Chunk 3"]


@pytest.mark.asyncio
async def test_execute_non_streaming(interaction_service):
    messages = [
        MessageModel(id=1, chat_id=1, role="user", content="Hello")
    ]
    
    response = await interaction_service.execute_non_streaming(
        url="http://test-url.com",
        model_name="test-model",
        messages=messages,
        provider="test-provider"
    )
    
    assert response == "Complete response"


@pytest.mark.asyncio
@patch("localchat.services.adapters.adapter_factory.AdapterFactory.get_adapter")
async def test_integration(mock_get_adapter, mock_adapter):
    mock_get_adapter.return_value = mock_adapter
    
    # Create real instances of strategies
    streaming_strategy = StreamingInteractionStrategy()
    non_streaming_strategy = NonStreamingInteractionStrategy()
    
    # Create the service with real strategies but mock adapter
    service = ModelInteractionService(
        streaming_strategy=streaming_strategy,
        non_streaming_strategy=non_streaming_strategy
    )
    
    messages = [
        MessageModel(id=1, chat_id=1, role="user", content="Hello")
    ]
    
    # Test non-streaming execution
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_response = AsyncMock()
        mock_response.raise_for_status = AsyncMock()
        mock_response.json.return_value = {"response": "Test API response"}
        mock_post.return_value = mock_response
        
        response = await service.execute_non_streaming(
            url="http://test-url.com",
            model_name="test-model",
            messages=messages,
            provider="test-provider"
        )
        
        assert response == "Test response"
        mock_adapter.format_url.assert_called_once()
        mock_adapter.format_request_payload.assert_called_once()
        mock_adapter.extract_response_text.assert_called_once()


if __name__ == "__main__":
    asyncio.run(pytest.main(["-xvs", __file__]))
