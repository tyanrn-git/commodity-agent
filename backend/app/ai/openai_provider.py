import json
from typing import TypeVar

from openai import OpenAI
from openai.lib._pydantic import to_strict_json_schema
from pydantic import BaseModel, ValidationError

from app.ai.base import AIProvider
from app.ai.pricing import estimate_cost_usd
from app.ai.schemas import AICompletionUsage
from app.config import settings

T = TypeVar("T", bound=BaseModel)


class OpenAIProvider(AIProvider):
    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or settings.openai_api_key
        if not key:
            raise ValueError("OPENAI_API_KEY is not configured")
        self.client = OpenAI(api_key=key)

    def structured_completion(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        output_schema: type[T],
        temperature: float = 0.0,
    ) -> tuple[T, AICompletionUsage]:
        schema = to_strict_json_schema(output_schema)
        response = self.client.chat.completions.create(
            model=model,
            temperature=temperature,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": output_schema.__name__,
                    "schema": schema,
                    "strict": True,
                },
            },
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        raw = json.loads(content)
        try:
            parsed = output_schema.model_validate(raw)
        except ValidationError as exc:
            raise ValueError(f"OpenAI output failed schema validation: {exc}") from exc

        usage_data = response.usage
        input_tokens = usage_data.prompt_tokens if usage_data else 0
        output_tokens = usage_data.completion_tokens if usage_data else 0
        usage = AICompletionUsage(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=estimate_cost_usd(model, input_tokens, output_tokens),
            raw_response=raw,
        )
        return parsed, usage
