from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

from app.ai.schemas import AICompletionUsage

T = TypeVar("T", bound=BaseModel)


class AIProvider(ABC):
    @abstractmethod
    def structured_completion(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[T],
        temperature: float = 0.0,
    ) -> tuple[T, AICompletionUsage]:
        """Return parsed structured output and usage metadata."""
