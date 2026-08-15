from typing import Any, TypeVar

from google import genai
from pydantic import BaseModel, ValidationError

from app.core.config import settings


StructuredOutputT = TypeVar(
    "StructuredOutputT",
    bound=BaseModel,
)

_UNSUPPORTED_GEMINI_JSON_SCHEMA_KEYS = frozenset(
    {
        "default",
        "minLength",
        "maxLength",
    }
)


def _sanitize_gemini_json_schema(
    value: Any,
) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize_gemini_json_schema(
                nested_value
            )
            for key, nested_value in value.items()
            if (
                key
                not in _UNSUPPORTED_GEMINI_JSON_SCHEMA_KEYS
            )
        }

    if isinstance(value, list):
        return [
            _sanitize_gemini_json_schema(item)
            for item in value
        ]

    return value


class LLMGatewayError(RuntimeError):
    pass


class LLMGatewayConfigurationError(LLMGatewayError):
    pass


class LLMInvalidOutputError(LLMGatewayError):
    pass


class LLMGateway:
    MAX_STRUCTURED_ATTEMPTS = 2

    def __init__(
        self,
        client: Any | None = None,
    ) -> None:
        if client is not None:
            self._client = client
            return

        if settings.gemini_api_key is None:
            raise LLMGatewayConfigurationError(
                "GEMINI_API_KEY is not configured"
            )

        self._client = genai.Client(
            api_key=(
                settings
                .gemini_api_key
                .get_secret_value()
            )
        )

    def generate_structured(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_model: type[StructuredOutputT],
    ) -> StructuredOutputT:
        failure_reasons: list[str] = []
        last_validation_error: (
            ValidationError | None
        ) = None

        provider_schema = (
            _sanitize_gemini_json_schema(
                response_model.model_json_schema()
            )
        )

        for attempt in range(
            1,
            self.MAX_STRUCTURED_ATTEMPTS + 1,
        ):
            current_system_prompt = system_prompt

            if attempt > 1:
                current_system_prompt = (
                    f"{system_prompt}\n\n"
                    "RETRY INSTRUCTION:\n"
                    "Your previous structured response was invalid. "
                    "Return a response that exactly matches the "
                    "required schema. Do not add commentary or "
                    "extra fields."
                )

            try:
                response = (
                    self._client
                    .models
                    .generate_content(
                        model=model,
                        contents=user_prompt,
                        config={
                            "system_instruction": (
                                current_system_prompt
                            ),
                            "response_mime_type": (
                                "application/json"
                            ),
                            "response_json_schema": (
                                provider_schema
                            ),
                        },
                    )
                )

            except Exception as exc:
                raise LLMGatewayError(
                    "LLM provider request failed"
                ) from exc

            output_text = response.text

            if not output_text:
                failure_reasons.append(
                    "empty_output"
                )
                continue

            try:
                return (
                    response_model
                    .model_validate_json(
                        output_text
                    )
                )

            except ValidationError as exc:
                failure_reasons.append(
                    "validation_error"
                )
                last_validation_error = exc

        error = LLMInvalidOutputError(
            "Structured output failed after "
            f"{self.MAX_STRUCTURED_ATTEMPTS} attempts. "
            f"Reasons: {failure_reasons}"
        )

        if last_validation_error is not None:
            raise error from last_validation_error

        raise error
