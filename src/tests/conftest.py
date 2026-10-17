import pytest
import os
import asyncio
from dataclasses import fields
from unittest.mock import AsyncMock, MagicMock, patch

# Set environment variables for testing
os.environ["DRY_RUN"] = "true"
os.environ["DEBUG"] = "true"


@pytest.fixture(autouse=True)
def restore_global_settings():
    """Prevent tests that mutate the frozen settings singleton from leaking state."""
    from src.settings import settings

    original = {field.name: getattr(settings, field.name) for field in fields(settings)}
    yield
    for name, value in original.items():
        object.__setattr__(settings, name, value)

@pytest.fixture
def mock_httpx_client():
    """Mock for httpx.AsyncClient."""
    mock = AsyncMock()
    # Default behavior for metadata and RSS fetches
    mock.get = AsyncMock()
    mock.post = AsyncMock()
    return mock

@pytest.fixture
def mock_bsky_client():
    """Mock for atproto.AsyncClient."""
    mock = AsyncMock()
    mock.login = AsyncMock(return_value=True)
    mock.send_post = AsyncMock(return_value=True)
    mock.upload_blob = AsyncMock()
    # Mocking the response with a blob
    mock_upload_response = MagicMock()
    mock_upload_response.blob = "mock_blob_id"
    mock.upload_blob.return_value = mock_upload_response
    mock.export_session_string = MagicMock(return_value="mock_session_str")
    return mock

@pytest.fixture
def mock_genai_client():
    """Mock for google.genai.Client."""
    mock = MagicMock()
    mock.aio = MagicMock()
    mock.aio.models = MagicMock()
    
    # Mock generate_content
    mock_response = AsyncMock()
    mock_response.text = "TOPIC: Science\nBODY: This is a mock summary from Gemini."
    mock.aio.models.generate_content = AsyncMock(return_value=mock_response)
    
    # Mock list models
    mock_model_list = [
        MagicMock(name="models/gemini-1.5-flash", supported_actions=["generateContent"]),
        MagicMock(name="models/gemma-2b-it", supported_actions=["generateContent"])
    ]
    mock.models.list = MagicMock(return_value=mock_model_list)
    
    return mock

@pytest.fixture(autouse=True)
def silent_logger():
    """Silence the SafeLogger during tests to keep output clean, unless we're testing the logger itself."""
    with patch("src.logger.SafeLogger.info"), \
         patch("src.logger.SafeLogger.warn"), \
         patch("src.logger.SafeLogger.error"), \
         patch("src.logger.SafeLogger.debug"):
        yield
