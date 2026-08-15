from uuid import uuid4

import pytest

from app.chat.context import (
    WorkingContext,
    WorkingMessage,
)
from app.schemas.intake import (
    IntakeExtraction,
    IntakeProvenance,
    ProfileField,
    ProfileFieldUpdate,
)
from app.services.intake_extraction import (
    IntakeExtractionService,
)


class FakeGateway:
    def __init__(
        self,
        result: IntakeExtraction,
    ) -> None:
        self.result = result
        self.calls = []

    def generate_structured(
        self,
        **kwargs,
    ):
        self.calls.append(
            kwargs
        )

        return self.result


def make_context(
    *,
    current_user_message: str = (
        "هستهدف أصحاب الجيمات في مصر"
    ),
) -> WorkingContext:
    return WorkingContext(
        idea_id=uuid4(),
        idea_title="Gym platform",
        idea_state="DRAFT",
        current_user_message=(
            current_user_message
        ),
        current_message_id=uuid4(),
        profile_version=1,
        profile_readiness="NOT_READY",
        profile_data={
            "idea_description": (
                "Software for gym management"
            ),
        },
        recent_messages=[
            WorkingMessage(
                role="assistant",
                content=(
                    "مين أول شريحة عملاء "
                    "عايز تستهدفها؟"
                ),
            ),
        ],
    )


def test_extract_uses_structured_intake_schema():
    extraction = IntakeExtraction(
        updates=[
            ProfileFieldUpdate(
                field=(
                    ProfileField
                    .TARGET_COUNTRY
                ),
                value="Egypt",
                provenance=(
                    IntakeProvenance.USER
                ),
                confidence=0.95,
            ),
        ],
    )

    gateway = FakeGateway(
        result=extraction,
    )

    service = IntakeExtractionService(
        gateway=gateway,
        model="test-model",
    )

    result = service.extract(
        make_context()
    )

    assert result == extraction

    assert len(
        gateway.calls
    ) == 1

    call = gateway.calls[0]

    assert (
        call["response_model"]
        is IntakeExtraction
    )

    assert (
        call["model"]
        == "test-model"
    )

    assert (
        "CURRENT USER MESSAGE"
        in call["user_prompt"]
    )

    assert (
        "هستهدف أصحاب الجيمات في مصر"
        in call["user_prompt"]
    )


def test_extract_includes_existing_profile_context():
    gateway = FakeGateway(
        result=IntakeExtraction()
    )

    service = IntakeExtractionService(
        gateway=gateway,
        model="test-model",
    )

    service.extract(
        make_context()
    )

    user_prompt = (
        gateway.calls[0][
            "user_prompt"
        ]
    )

    assert (
        "idea_description"
        in user_prompt
    )

    assert (
        "Software for gym management"
        in user_prompt
    )


def test_extract_includes_recent_messages():
    gateway = FakeGateway(
        result=IntakeExtraction()
    )

    service = IntakeExtractionService(
        gateway=gateway,
        model="test-model",
    )

    service.extract(
        make_context()
    )

    user_prompt = (
        gateway.calls[0][
            "user_prompt"
        ]
    )

    assert (
        "مين أول شريحة عملاء"
        in user_prompt
    )


def test_extract_rejects_empty_current_message():
    gateway = FakeGateway(
        result=IntakeExtraction()
    )

    service = IntakeExtractionService(
        gateway=gateway,
        model="test-model",
    )

    context = make_context(
        current_user_message="   ",
    )

    with pytest.raises(
        ValueError,
        match=(
            "current_user_message "
            "cannot be empty"
        ),
    ):
        service.extract(
            context
        )

    assert (
        gateway.calls
        == []
    )