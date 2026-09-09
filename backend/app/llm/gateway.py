import logging
from typing import Any, TypeVar

from google import genai
from pydantic import BaseModel, ValidationError

from app.core.config import settings

logger = logging.getLogger(__name__)


def _is_fallback_worthy_error(exc: Exception) -> bool:
    """Return True only for transient/provider-capacity failures.

    Model fallback is a transport/resilience mechanism. It must not hide prompt,
    schema, or structured-output regressions by silently changing models.
    """
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if code in (429, 500, 502, 503, 504):
        return True

    text = str(exc).lower()
    fallback_indicators = (
        "429",
        "resource_exhausted",
        "resourceexhausted",
        "quota",
        "rate limit",
        "ratelimit",
        "rate_limit",
        "too many requests",
        "exhausted",
        "overloaded",
        "temporarily unavailable",
        "capacity",
        "503",
        "service unavailable",
        "deadline exceeded",
        "timeout",
    )
    return any(indicator in text for indicator in fallback_indicators)


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

    candidates = getattr(response, "candidates", None)
    if candidates and len(candidates) > 0:
        candidate = candidates[0]
        finish_reason = getattr(candidate, "finish_reason", None)
        if finish_reason:
            details.append(f"finish_reason={finish_reason}")

        finish_message = getattr(candidate, "finish_message", None)
        if finish_message:
            details.append(f"finish_message={finish_message}")

    prompt_feedback = getattr(response, "prompt_feedback", None)
    if prompt_feedback:
        block_reason = getattr(prompt_feedback, "block_reason", None)
        if block_reason:
            details.append(f"block_reason={block_reason}")

    if not details:
        return ""

    return f" ({', '.join(details)})"


def _sanitize_gemini_json_schema(value: Any) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}

        for key, nested_value in value.items():
            if key in _UNSUPPORTED_GEMINI_JSON_SCHEMA_KEYS:
                continue

            if (
                key == "format"
                and nested_value not in _SUPPORTED_GEMINI_STRING_FORMATS
            ):
                continue

            sanitized[key] = _sanitize_gemini_json_schema(nested_value)

        return sanitized

    if isinstance(value, list):
        return [_sanitize_gemini_json_schema(item) for item in value]

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
        fallback_models: list[str] | None = None,
    ) -> None:
        self._fallback_models = (
            list(fallback_models)
            if fallback_models is not None
            else list(settings.llm_fallback_models)
        )

        if client is not None:
            self._client = client
            return

        if settings.gemini_api_key is None:
            raise LLMGatewayConfigurationError(
                "GEMINI_API_KEY is not configured"
            )

        self._client = genai.Client(
            api_key=settings.gemini_api_key.get_secret_value()
        )

    def _candidate_models(self, requested_model: str) -> list[str]:
        candidates = [requested_model]
        for fallback_model in self._fallback_models:
            if fallback_model not in candidates:
                candidates.append(fallback_model)
        return candidates

    def generate_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        models_to_try = self._candidate_models(model)
        config: dict[str, Any] = {}

        if system_prompt.strip():
            config["system_instruction"] = system_prompt

        last_provider_error: Exception | None = None

        for index, current_model in enumerate(models_to_try):
            has_fallback = index + 1 < len(models_to_try)
            next_model = models_to_try[index + 1] if has_fallback else None

            try:
                response = self._client.models.generate_content(
                    model=current_model,
                    contents=user_prompt,
                    config=config,
                )
            except Exception as exc:
                last_provider_error = exc
                if has_fallback and _is_fallback_worthy_error(exc):
                    logger.warning(
                        "LLM text request to model '%s' failed with a transient provider error (%s). Falling back to '%s'.",
                        current_model,
                        exc,
                        next_model,
                    )
                    continue

                raise LLMGatewayError(
                    f"LLM provider request failed for model '{current_model}': {exc}"
                ) from exc

            try:
                output_text = response.text
            except Exception:
                output_text = None

            if not output_text:
                diagnostic = _extract_response_diagnostic(response)
                raise LLMInvalidOutputError(
                    f"LLM returned empty text output{diagnostic}"
                )

            return output_text

        raise LLMGatewayError(
            f"All candidate models {models_to_try} failed with transient provider errors: {last_provider_error}"
        )

    def generate_structured(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_model: type[StructuredOutputT],
    ) -> StructuredOutputT:
        models_to_try = self._candidate_models(model)
        provider_schema = _sanitize_gemini_json_schema(
            response_model.model_json_schema()
        )

        transient_failures: list[str] = []
        last_provider_error: Exception | None = None

        for model_index, current_model in enumerate(models_to_try):
            has_fallback = model_index + 1 < len(models_to_try)
            next_model = (
                models_to_try[model_index + 1]
                if has_fallback
                else None
            )
            failure_reasons: list[str] = []
            last_validation_error: ValidationError | None = None
            switch_to_next_model = False

            for attempt in range(1, self.MAX_STRUCTURED_ATTEMPTS + 1):
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
                    response = self._client.models.generate_content(
                        model=current_model,
                        contents=user_prompt,
                        config={
                            "system_instruction": current_system_prompt,
                            "response_mime_type": "application/json",
                            "response_json_schema": provider_schema,
                        },
                    )
                except Exception as exc:
                    last_provider_error = exc
                    if has_fallback and _is_fallback_worthy_error(exc):
                        logger.warning(
                            "LLM structured request to model '%s' failed with a transient provider error (%s). Falling back to '%s'.",
                            current_model,
                            exc,
                            next_model,
                        )
                        transient_failures.append(
                            f"{current_model}: {exc}"
                        )
                        switch_to_next_model = True
                        break

                    raise LLMGatewayError(
                        f"LLM provider request failed for model '{current_model}': {exc}"
                    ) from exc

                try:
                    output_text = response.text
                except Exception:
                    output_text = None

                if not output_text:
                    diagnostic = _extract_response_diagnostic(response)
                    failure_reasons.append(f"empty_output{diagnostic}")
                    continue

                try:
                    return response_model.model_validate_json(output_text)
                except ValidationError as exc:
                    last_validation_error = exc
                    failure_reasons.append("validation_error")

            if switch_to_next_model:
                continue

            error = LLMInvalidOutputError(
                f"Structured output from model '{current_model}' failed after "
                f"{self.MAX_STRUCTURED_ATTEMPTS} attempts. Reasons: {failure_reasons}"
            )
            if last_validation_error is not None:
                raise error from last_validation_error
            raise error

        raise LLMGatewayError(
            f"All candidate models {models_to_try} failed with transient provider errors: {transient_failures or last_provider_error}"
        )
