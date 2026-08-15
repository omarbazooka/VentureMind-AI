from importlib.metadata import version

from google import genai

from app.core.config import settings
from app.llm.gateway import _sanitize_gemini_json_schema
from app.schemas.intake import IntakeExtraction


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


def _safe_error(exc: Exception, api_key: str) -> str:
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
    print(f"google-genai version: {sdk_version}")
    print(f"model: {model}")
    print("API key configured: YES")


def main() -> int:
    if settings.gemini_api_key is None:
        print("FAIL: GEMINI_API_KEY is not configured")
        return 1

    api_key = (
        settings
        .gemini_api_key
        .get_secret_value()
    )
    model = settings.turn_understanding_model

    try:
        sdk_version = version("google-genai")
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
    print("STAGE 1 - plain text generation")
    print("-" * 70)

    try:
        response = client.models.generate_content(
            model=model,
            contents="Reply with exactly: OK",
        )
        print(f"PASS: {response.text!r}")
    except Exception as exc:
        print("FAIL:")
        print(_safe_error(exc, api_key))
        print()
        print(
            "DIAGNOSIS: the failure is below structured output. "
            "Check provider access, API key/project, model access, "
            "quota/billing, or SDK/provider connectivity."
        )
        return 1

    print()
    print("STAGE 2 - minimal structured output")
    print("-" * 70)

    try:
        response = client.models.generate_content(
            model=model,
            contents=(
                "Return an object where ok is true."
            ),
            config={
                "response_mime_type": "application/json",
                "response_json_schema": TINY_SCHEMA,
            },
        )
        print(f"PASS: {response.text!r}")
    except Exception as exc:
        print("FAIL:")
        print(_safe_error(exc, api_key))
        print()
        print(
            "DIAGNOSIS: plain generation works, but even a tiny "
            "structured schema fails. The issue is in structured-output "
            "support/SDK-provider compatibility, not VentureMind Intake."
        )
        return 1

    print()
    print("STAGE 3 - VentureMind Intake schema")
    print("-" * 70)

    intake_schema = _sanitize_gemini_json_schema(
        IntakeExtraction.model_json_schema()
    )

    try:
        response = client.models.generate_content(
            model=model,
            contents=(
                "The user explicitly said their target country is Egypt. "
                "Extract only that explicit profile fact."
            ),
            config={
                "response_mime_type": "application/json",
                "response_json_schema": intake_schema,
            },
        )
        result = IntakeExtraction.model_validate_json(
            response.text
        )
        print(
            "PASS: "
            + result.model_dump_json(indent=2)
        )
    except Exception as exc:
        print("FAIL:")
        print(_safe_error(exc, api_key))
        print()
        print(
            "DIAGNOSIS: basic structured output works, but the "
            "VentureMind Intake schema fails. The remaining problem is "
            "schema-specific and can be isolated without touching auth "
            "or the model configuration."
        )
        return 1

    print()
    print("=" * 70)
    print("DIAGNOSTIC RESULT: PASS")
    print(
        "Provider access, model access, minimal structured output, and "
        "the VentureMind Intake schema all work."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
