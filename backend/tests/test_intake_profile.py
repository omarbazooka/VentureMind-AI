import pytest

from app.schemas.intake import (
    IntakeProvenance,
    ProfileField,
    ProfileFieldUpdate,
)
from app.services.intake_profile import (
    ProfileValueValidationError,
    build_candidate_profile_data,
    validate_and_normalize_update,
)


def make_update(
    *,
    field: ProfileField,
    value,
) -> ProfileFieldUpdate:
    return ProfileFieldUpdate(
        field=field,
        value=value,
        provenance=IntakeProvenance.USER,
        confidence=0.95,
    )


def test_text_value_is_normalized():
    update = make_update(
        field=ProfileField.TARGET_CITY,
        value="  Cairo  ",
    )

    validated = validate_and_normalize_update(
        update
    )

    assert validated.value == "Cairo"


def test_budget_accepts_numeric_value():
    update = make_update(
        field=ProfileField.BUDGET,
        value=300000,
    )

    validated = validate_and_normalize_update(
        update
    )

    assert validated.value == 300000


def test_budget_rejects_text_value():
    update = make_update(
        field=ProfileField.BUDGET,
        value="three hundred thousand",
    )

    with pytest.raises(
        ProfileValueValidationError,
        match="budget must be numeric",
    ):
        validate_and_normalize_update(update)


def test_budget_rejects_boolean_value():
    update = make_update(
        field=ProfileField.BUDGET,
        value=True,
    )

    with pytest.raises(
        ProfileValueValidationError,
        match="budget must be numeric",
    ):
        validate_and_normalize_update(update)


def test_text_list_is_normalized():
    update = make_update(
        field=ProfileField.TARGET_CUSTOMERS,
        value=[
            "  Personal trainers ",
            "Gym members  ",
        ],
    )

    validated = validate_and_normalize_update(
        update
    )

    assert validated.value == [
        "Personal trainers",
        "Gym members",
    ]


def test_candidate_merge_does_not_mutate_current_data():
    current_data = {
        "target_country": "Egypt",
    }

    update = make_update(
        field=ProfileField.BUDGET,
        value=300000,
    )

    candidate = build_candidate_profile_data(
        current_data=current_data,
        updates=[update],
    )

    assert current_data == {
        "target_country": "Egypt",
    }

    assert candidate == {
        "target_country": "Egypt",
        "budget": 300000,
    }