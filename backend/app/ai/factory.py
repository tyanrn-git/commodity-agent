from app.ai.base import AIProvider
from app.ai.mock_provider import MockAIProvider
from app.ai.openai_provider import OpenAIProvider
from app.config import settings


def get_ai_provider() -> AIProvider:
    if settings.ai_provider == "mock" or not settings.openai_api_key:
        return MockAIProvider()
    return OpenAIProvider()
