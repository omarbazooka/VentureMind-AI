from uuid import uuid4

import pytest

from app.chat.context import (
    WorkingContext,
    WorkingMessage,
)
from app.schemas.intake import (
    IntakeProvenance,
    ProfileField,
    ProfileValueKind,
)
from app.services.intake_extraction import (
    IntakeExtractionService,
    LLMIntakeExtraction,
    LLMProfileFieldUpdate,
)


class FakeGateway:
    def __init__(
        self,
        result: LLMIntakeExtraction,
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


def make_provider_extraction(
    *,
    field: ProfileField = (
        ProfileField.TARGET_COUNTRY
    ),
    value: str = "Egypt",
    value_kind: ProfileValueKind = (
        ProfileValueKind.FACT
    ),
) -> LLMIntakeExtraction:
    return LLMIntakeExtraction(
        updates=[
            LLMProfileFieldUpdate(
                field=field,
                value=value,
                value_kind=value_kind,
                confidence=0.95,
            ),
        ],
        unknown_fields=[],
    )


def _contains_key(
    value,
    key: str,
) -> bool:
    if isinstance(value, dict):
        if key in value:
            return True

        return any(
            _contains_key(
                nested_value,
                key,
            )
            for nested_value
            in value.values()
        )

    if isinstance(value, list):
        return any(
            _contains_key(
                item,
                key,
            )
            for item in value
        )

    return False


def test_extract_uses_provider_safe_schema_and_returns_domain_extraction():
    gateway = FakeGateway(
        result=make_provider_extraction()
    )

    service = IntakeExtractionService(
        gateway=gateway,
        model="test-model",
    )

    result = service.extract(
        make_context()
    )

    assert len(
        result.updates
    ) == 1

    update = result.updates[0]

    assert (
        update.field
        == ProfileField.TARGET_COUNTRY
    )
    assert update.value == "Egypt"
    assert (
        update.provenance
        == IntakeProvenance.USER
    )
    assert (
        update.value_kind
        == ProfileValueKind.FACT
    )

    assert len(
        gateway.calls
    ) == 1

    call = gateway.calls[0]

    assert (
        call["response_model"]
        is LLMIntakeExtraction
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


def test_extract_converts_budget_string_to_number():
    gateway = FakeGateway(
        result=make_provider_extraction(
            field=ProfileField.BUDGET,
            value="500000",
        )
    )

    service = IntakeExtractionService(
        gateway=gateway,
        model="test-model",
    )

    result = service.extract(
        make_context(
            current_user_message=(
                "الميزانية 500 ألف جنيه"
            )
        )
    )

    update = result.updates[0]

    assert (
        update.field
        == ProfileField.BUDGET
    )
    assert update.value == 500000
    assert isinstance(
        update.value,
        int,
    )


def test_provider_schema_avoids_profile_value_union():
    schema = (
        LLMIntakeExtraction
        .model_json_schema()
    )

    assert not _contains_key(
        schema,
        "anyOf",
    )


def test_provider_schema_requires_value_kind_and_arrays():
    schema = (
        LLMIntakeExtraction
        .model_json_schema()
    )

    assert set(
        schema["required"]
    ) == {
        "updates",
        "unknown_fields",
    }

    update_required = set(
        schema["$defs"][
            "LLMProfileFieldUpdate"
        ][
            "required"
        ]
    )

    assert update_required == {
        "field",
        "value",
        "value_kind",
        "confidence",
    }


def test_provider_budget_rejects_non_numeric_value():
    with pytest.raises(
        ValueError,
        match=(
            "budget extraction "
            "must be a plain number"
        ),
    ):
        make_provider_extraction(
            field=ProfileField.BUDGET,
            value="500 thousand EGP",
        )


def test_extract_includes_existing_profile_context():
    gateway = FakeGateway(
        result=LLMIntakeExtraction(
            updates=[],
            unknown_fields=[],
        )
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
        result=LLMIntakeExtraction(
            updates=[],
            unknown_fields=[],
        )
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
        result=LLMIntakeExtraction(
            updates=[],
            unknown_fields=[],
        )
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
