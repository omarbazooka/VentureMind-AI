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
        "minItems",
        "maxItems",
    }
)

_SUPPORTED_GEMINI_STRING_FORMATS = frozenset(
    {
        "date-time",
        "date",
        "time",
    }
)


def _extract_response_diagnostic(
    response: Any,
) -> str:
    details: list[str] = []

    candidates = getattr(
        response,
        "candidates",
        None,
    )
    if candidates and len(candidates) > 0:
        c = candidates[0]
        finish_reason = getattr(
            c,
            "finish_reason",
            None,
        )
        if finish_reason:
            details.append(
                f"finish_reason={finish_reason}"
            )

        finish_message = getattr(
            c,
            "finish_message",
            None,
        )
        if finish_message:
            details.append(
                f"finish_message={finish_message}"
            )

    prompt_feedback = getattr(
        response,
        "prompt_feedback",
        None,
    )
    if prompt_feedback:
        block_reason = getattr(
            prompt_feedback,
            "block_reason",
            None,
        )
        if block_reason:
            details.append(
                f"block_reason={block_reason}"
            )

    if not details:
        return ""

    return f" ({', '.join(details)})"


def _sanitize_gemini_json_schema(
    value: Any,
) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}

        for key, nested_value in value.items():
            if (
                key
                in _UNSUPPORTED_GEMINI_JSON_SCHEMA_KEYS
            ):
                continue

            if (
                key == "format"
                and nested_value
                not in _SUPPORTED_GEMINI_STRING_FORMATS
            ):
                continue

            sanitized[key] = (
                _sanitize_gemini_json_schema(
                    nested_value
                )
            )

        return sanitized

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

    def generate_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        config: dict[str, Any] = {}

        if system_prompt.strip():
            config["system_instruction"] = (
                system_prompt
            )

        try:
            response = (
                self._client
                .models
                .generate_content(
                    model=model,
                    contents=user_prompt,
                    config=config,
                )
            )

        except Exception as exc:
            raise LLMGatewayError(
                f"LLM provider request failed: {exc}"
            ) from exc

        try:
            output_text = response.text
        except Exception:
            output_text = None

        if not output_text:
            diag = _extract_response_diagnostic(
                response
            )
            raise LLMInvalidOutputError(
                f"LLM returned empty text output{diag}"
            )

        return output_text

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
                    f"LLM provider request failed: {exc}"
                ) from exc

            try:
                output_text = response.text
            except Exception:
                output_text = None

            if not output_text:
                diag = _extract_response_diagnostic(
                    response
                )
                failure_reasons.append(
                    f"empty_output{diag}"
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

