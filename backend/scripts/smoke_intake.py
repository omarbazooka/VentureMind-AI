from uuid import uuid4

from app.chat.context import WorkingContext
from app.services.intake_extraction import (
    IntakeExtractionService,
)


CASES = [
    "عايز أعمل SaaS لإدارة الجيمات في مصر.",

    (
        "هستهدف أصحاب الجيمات المستقلة، "
        "والميزانية المبدئية حوالي 500 ألف جنيه."
    ),

    (
        "أنا مش عارف الـ revenue model لسه."
    ),

    (
        "خلينا نفترض مؤقتًا إن الاشتراك "
        "هيكون 2000 جنيه شهريًا."
    ),

    (
        "بدل مصر أنا بفكر أبدأ في السعودية."
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


def main() -> None:
    service = IntakeExtractionService()

    for index, message in enumerate(
        CASES,
        start=1,
    ):
        print(
            f"\n{'=' * 70}"
        )
        print(
            f"CASE {index}"
        )
        print(
            f"USER: {message}"
        )
        print(
            "-" * 70
        )

        result = service.extract(
            build_context(message)
        )

        print(
            result.model_dump_json(
                indent=2,
            )
        )


if __name__ == "__main__":
    main()