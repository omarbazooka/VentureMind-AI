from importlib.metadata import version

from google import genai

from app.core.config import settings
from app.llm.gateway import _sanitize_gemini_json_schema
from app.services.intake_extraction import (
    LLMIntakeExtraction,
)


TINY_SCHEMA = {
    "type": "object",
    "properties": {
        "ok": {
            "type": "boolean",
        },
    },
    "required": ["ok"],
    "additionalProperties": False,
}


def _safe_error(
    exc: Exception,
    api_key: str,
) -> str:
    text = str(exc)

    if api_key:
        text = text.replace(
            api_key,
            "[REDACTED_API_KEY]",
        )

    return (
        f"{type(exc).__module__}."
        f"{type(exc).__name__}: {text}"
    )


def _print_header(
    *,
    sdk_version: str,
    model: str,
) -> None:
    print("=" * 70)
    print("GEMINI PROVIDER DIAGNOSTIC")
    print("=" * 70)
    print(
        f"google-genai version: "
        f"{sdk_version}"
    )
    print(f"model: {model}")
    print("API key configured: YES")


def main() -> int:
    if settings.gemini_api_key is None:
        print(
            "FAIL: GEMINI_API_KEY "
            "is not configured"
        )
        return 1

    api_key = (
        settings
        .gemini_api_key
        .get_secret_value()
    )
    model = (
        settings
        .turn_understanding_model
    )

    try:
        sdk_version = version(
            "google-genai"
        )
    except Exception:
        sdk_version = "unknown"

    _print_header(
        sdk_version=sdk_version,
        model=model,
    )

    client = genai.Client(
        api_key=api_key,
    )

    print()
    print(
        "STAGE 1 - plain text generation"
    )
    print("-" * 70)

    try:
        response = (
            client.models.generate_content(
                model=model,
                contents=(
                    "Reply with exactly: OK"
                ),
            )
        )
        print(
            f"PASS: {response.text!r}"
        )
    except Exception as exc:
        print("FAIL:")
        print(
            _safe_error(
                exc,
                api_key,
            )
        )
        return 1

    print()
    print(
        "STAGE 2 - minimal structured output"
    )
    print("-" * 70)

    try:
        response = (
            client.models.generate_content(
                model=model,
                contents=(
                    "Return an object "
                    "where ok is true."
                ),
                config={
                    "response_mime_type": (
                        "application/json"
                    ),
                    "response_json_schema": (
                        TINY_SCHEMA
                    ),
                },
            )
        )
        print(
            f"PASS: {response.text!r}"
        )
    except Exception as exc:
        print("FAIL:")
        print(
            _safe_error(
                exc,
                api_key,
            )
        )
        return 1

    print()
    print(
        "STAGE 3 - provider-safe "
        "VentureMind Intake schema"
    )
    print("-" * 70)

    intake_schema = (
        _sanitize_gemini_json_schema(
            LLMIntakeExtraction
            .model_json_schema()
        )
    )

    try:
        response = (
            client.models.generate_content(
                model=model,
                contents=(
                    "The user explicitly said "
                    "their target country is Egypt. "
                    "Return updates with one "
                    "target_country FACT whose "
                    "string value is Egypt, and "
                    "return an empty unknown_fields "
                    "array."
                ),
                config={
                    "response_mime_type": (
                        "application/json"
                    ),
                    "response_json_schema": (
                        intake_schema
                    ),
                },
            )
        )

        result = (
            LLMIntakeExtraction
            .model_validate_json(
                response.text
            )
        )

        print(
            "PASS: "
            + result.model_dump_json(
                indent=2
            )
        )
    except Exception as exc:
        print("FAIL:")
        print(
            _safe_error(
                exc,
                api_key,
            )
        )
        return 1

    print()
    print("=" * 70)
    print(
        "DIAGNOSTIC RESULT: PASS"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
