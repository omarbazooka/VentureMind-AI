from uuid import uuid4

from app.chat.context import WorkingContext
from app.chat.turn_understanding import (
    TurnUnderstandingService,
)
from app.llm.gateway import LLMGatewayError


SMOKE_CASES = [
    "Hello",
    "My target customers are small restaurants in Egypt.",
    "Start the analysis.",
    "Change my budget to 500000 EGP.",
    (
        "Change my budget to 500000 EGP "
        "and rerun the scenario."
    ),
    "Do it.",
    (
        "Change my budget to 500000 EGP, "
        "actually keep the old budget."
    ),
]


def build_context(
    message: str,
) -> WorkingContext:
    return WorkingContext(
        idea_id=uuid4(),
        idea_title="Smoke Test Idea",
        idea_state="DRAFT",
        current_user_message=message,
        current_message_id=uuid4(),
        profile_version=1,
        profile_readiness="NOT_READY",
        profile_data={
            "target_country": "Egypt",
            "budget": 250000,
            "currency": "EGP",
        },
        recent_messages=[],
    )


def main() -> int:
    service = TurnUnderstandingService()
    failures = 0

    for index, message in enumerate(
        SMOKE_CASES,
        start=1,
    ):
        print()
        print("=" * 70)
        print(f"CASE {index}")
        print(f"USER: {message}")
        print("-" * 70)

        try:
            result = service.understand(
                message,
                build_context(message),
            )

        except LLMGatewayError as exc:
            failures += 1
            print(
                "FAIL - LLM ERROR: "
                f"{type(exc).__name__}: {exc}"
            )
            continue

        except ValueError as exc:
            failures += 1
            print(
                f"FAIL - INPUT ERROR: {exc}"
            )
            continue

        print(
            result.model_dump_json(
                indent=2
            )
        )
        print("PASS")

    print()
    print("=" * 70)

    if failures:
        print(
            f"SMOKE RESULT: FAIL "
            f"({failures} case(s) failed)"
        )
        return 1

    print("SMOKE RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
