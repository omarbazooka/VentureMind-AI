from uuid import uuid4

from app.chat.context import WorkingContext
from app.llm.gateway import LLMGatewayError
from app.schemas.intake import (
    ProfileField,
    ProfileValueKind,
)
from app.services.intake_extraction import (
    IntakeExtractionService,
)


CASES = [
    (
        "basic idea",
        "عايز أعمل SaaS لإدارة الجيمات في مصر.",
    ),
    (
        "customers and budget",
        (
            "هستهدف أصحاب الجيمات المستقلة، "
            "والميزانية المبدئية حوالي 500 ألف جنيه."
        ),
    ),
    (
        "declared unknown",
        "أنا مش عارف الـ revenue model لسه.",
    ),
    (
        "explicit working assumption",
        (
            "خلينا نفترض مؤقتًا إن العميل المستهدف "
            "هو أصحاب الجيمات المستقلة."
        ),
    ),
    (
        "possible contradiction",
        "بدل مصر أنا بفكر أبدأ في السعودية.",
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
        },
        recent_messages=[],
    )


def validate_case(
    index: int,
    result,
) -> list[str]:
    update_fields = {
        update.field
        for update in result.updates
    }
    unknown_fields = set(
        result.unknown_fields
    )
    problems: list[str] = []

    if (
        index == 1
        and ProfileField.TARGET_COUNTRY
        not in update_fields
    ):
        problems.append(
            "expected target_country extraction"
        )

    if index == 2:
        for expected_field in (
            ProfileField.TARGET_CUSTOMERS,
            ProfileField.BUDGET,
        ):
            if expected_field not in update_fields:
                problems.append(
                    "expected extraction for "
                    f"{expected_field.value}"
                )

    if (
        index == 3
        and ProfileField.REVENUE_MODEL
        not in unknown_fields
    ):
        problems.append(
            "expected revenue_model in unknown_fields"
        )

    if index == 4:
        if not any(
            update.value_kind
            == ProfileValueKind.ASSUMPTION
            for update in result.updates
        ):
            problems.append(
                "expected at least one ASSUMPTION update"
            )

    if (
        index == 5
        and ProfileField.TARGET_COUNTRY
        not in update_fields
    ):
        problems.append(
            "expected proposed target_country update"
        )

    return problems


def main() -> int:
    service = IntakeExtractionService()
    failures = 0

    for index, (
        label,
        message,
    ) in enumerate(
        CASES,
        start=1,
    ):
        print()
        print("=" * 70)
        print(
            f"CASE {index}: {label}"
        )
        print(f"USER: {message}")
        print("-" * 70)

        try:
            result = service.extract(
                build_context(message)
            )

        except (
            LLMGatewayError,
            ValueError,
        ) as exc:
            failures += 1
            print(
                "FAIL - "
                f"{type(exc).__name__}: {exc}"
            )
            continue

        print(
            result.model_dump_json(
                indent=2,
            )
        )

        problems = validate_case(
            index,
            result,
        )

        if problems:
            failures += 1
            print(
                "FAIL - "
                + "; ".join(problems)
            )
        else:
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
