import pytest
import respx
from httpx import Response
from backend.config import OPENROUTER_API_URL

@pytest.fixture
def mock_openrouter():
    """Mock the OpenRouter API requests."""
    with respx.mock(base_url="https://openrouter.ai", assert_all_called=False) as respx_mock:
        # Default mock for the completion endpoint
        # We match on any POST to the completions URL
        route = respx_mock.post("/api/v1/chat/completions")
        route.return_value = Response(
            200, 
            json={
                "id": "gen-123",
                "choices": [{"message": {"content": "mocked response", "reasoning_details": "thoughts"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20}
            }
        )
        yield respx_mock
