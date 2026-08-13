import pytest

from app.schemas.intake import (
    IntakeProvenance,
    ProfileField,
    ProfileFieldUpdate,
)
from app.services.intake_profile import (
    ProfileValueValidationError,
    validate_and_normalize_update,
    plan_profile_merge,
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


def test_merge_accepts_new_field_without_mutating_current_data():
    current_data = {
        "target_country": "Egypt",
    }

    update = make_update(
        field=ProfileField.BUDGET,
        value=300000,
    )

    plan = plan_profile_merge(
        current_data=current_data,
        updates=[update],
    )

    assert current_data == {
        "target_country": "Egypt",
    }

    assert plan.candidate_profile_data == {
        "target_country": "Egypt",
        "budget": 300000,
    }

    assert plan.accepted_updates == [
        update
    ]

    assert plan.conflicts == []


def test_same_value_is_unchanged_not_conflict():
    current_data = {
        "target_city": "Cairo",
    }

    update = make_update(
        field=ProfileField.TARGET_CITY,
        value=" cairo ",
    )

    plan = plan_profile_merge(
        current_data=current_data,
        updates=[update],
    )

    assert plan.conflicts == []

    assert plan.accepted_updates == []

    assert plan.unchanged_fields == [
        ProfileField.TARGET_CITY
    ]

    assert plan.candidate_profile_data == {
        "target_city": "Cairo",
    }


def test_changed_existing_value_creates_conflict():
    current_data = {
        "target_city": "Cairo",
    }

    update = make_update(
        field=ProfileField.TARGET_CITY,
        value="Alexandria",
    )

    plan = plan_profile_merge(
        current_data=current_data,
        updates=[update],
    )

    assert plan.accepted_updates == []

    assert len(plan.conflicts) == 1

    conflict = plan.conflicts[0]

    assert (
        conflict.field
        == ProfileField.TARGET_CITY
    )

    assert conflict.current_value == "Cairo"
    assert conflict.proposed_value == "Alexandria"

    assert plan.candidate_profile_data == {
        "target_city": "Cairo",
    }

def test_list_order_does_not_create_false_conflict():
    current_data = {
        "target_customers": [
            "Personal Trainers",
            "Gym Members",
        ]
    }

    update = make_update(
        field=ProfileField.TARGET_CUSTOMERS,
        value=[
            "gym members",
            "personal trainers",
        ],
    )

    plan = plan_profile_merge(
        current_data=current_data,
        updates=[update],
    )

    assert plan.conflicts == []

    assert plan.unchanged_fields == [
        ProfileField.TARGET_CUSTOMERS
    ]


def test_merge_accepts_safe_updates_and_preserves_conflicts():
    current_data = {
        "target_city": "Cairo",
    }

    updates = [
        make_update(
            field=ProfileField.TARGET_CITY,
            value="Alexandria",
        ),
        make_update(
            field=ProfileField.BUDGET,
            value=300000,
        ),
    ]

    plan = plan_profile_merge(
        current_data=current_data,
        updates=updates,
    )

    assert len(plan.conflicts) == 1

    assert [
        update.field
        for update in plan.accepted_updates
    ] == [
        ProfileField.BUDGET
    ]

    assert plan.candidate_profile_data == {
        "target_city": "Cairo",
        "budget": 300000,
    }