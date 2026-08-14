import pytest

from app.schemas.intake import (
    IntakeProvenance,
    ProfileField,
    ProfileFieldMetadata,
    ProfileFieldUpdate,
    ProfileReadinessStatus,
    ProfileValueKind,
)
from app.services.intake_profile import (
    ProfileValueValidationError,
    evaluate_profile_readiness,
    plan_profile_merge,
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

def make_metadata(
    *,
    provenance: IntakeProvenance = (
        IntakeProvenance.USER
    ),
) -> dict:
    return ProfileFieldMetadata(
        provenance=provenance,
        value_kind=ProfileValueKind.FACT,
        confidence=0.95,
    ).model_dump(
        mode="json"
    )

def test_empty_profile_is_not_ready():
    result = evaluate_profile_readiness(
        profile_data={},
        profile_metadata={},
        unknown_fields=[],
    )

    assert (
        result.readiness
        == ProfileReadinessStatus.NOT_READY
    )

    assert result.missing_critical_fields == [
        ProfileField.IDEA_DESCRIPTION,
        ProfileField.TARGET_CUSTOMERS,
        ProfileField.TARGET_COUNTRY,
    ]


def test_minimum_grounded_profile_is_ready():
    profile_data = {
        "idea_description": (
            "A meal subscription service "
            "for diabetic adults"
        ),
        "target_customers": (
            "Adults with type 2 diabetes"
        ),
        "target_country": "Egypt",
    }

    profile_metadata = {
        field_name: make_metadata()
        for field_name
        in profile_data
    }

    result = evaluate_profile_readiness(
        profile_data=profile_data,
        profile_metadata=profile_metadata,
        unknown_fields=[],
    )

    assert (
        result.readiness
        == (
            ProfileReadinessStatus
            .READY_FOR_ANALYSIS
        )
    )

    assert (
        result.missing_critical_fields
        == []
    )


def test_problem_and_solution_satisfy_core_idea():
    profile_data = {
        "problem": (
            "Restaurants waste surplus food"
        ),
        "proposed_solution": (
            "A marketplace for discounted "
            "surplus meals"
        ),
        "target_customers": (
            "Budget-conscious consumers"
        ),
        "target_country": "Egypt",
    }

    profile_metadata = {
        field_name: make_metadata()
        for field_name
        in profile_data
    }

    result = evaluate_profile_readiness(
        profile_data=profile_data,
        profile_metadata=profile_metadata,
        unknown_fields=[],
    )

    assert (
        result.readiness
        == (
            ProfileReadinessStatus
            .READY_FOR_ANALYSIS
        )
    )

def test_ai_assumption_cannot_force_readiness():
    profile_data = {
        "idea_description": "Delivery app",
        "target_customers": "Students",
        "target_country": "Egypt",
    }

    profile_metadata = {
        "idea_description": make_metadata(),
        "target_customers": make_metadata(),
        "target_country": make_metadata(
            provenance=(
                IntakeProvenance.AI_ASSUMPTION
            )
        ),
    }

    result = evaluate_profile_readiness(
        profile_data=profile_data,
        profile_metadata=profile_metadata,
        unknown_fields=[],
    )

    assert (
        result.readiness
        == ProfileReadinessStatus.NOT_READY
    )

    assert (
        ProfileField.TARGET_COUNTRY
        in result.missing_critical_fields
    )

def test_unknown_critical_field_blocks_readiness():
    profile_data = {
        "idea_description": "Delivery app",
        "target_customers": "Students",
    }

    profile_metadata = {
        "idea_description": make_metadata(),
        "target_customers": make_metadata(),
    }

    result = evaluate_profile_readiness(
        profile_data=profile_data,
        profile_metadata=profile_metadata,
        unknown_fields=[
            "target_country",
        ],
    )

    assert (
        result.readiness
        == ProfileReadinessStatus.NOT_READY
    )

    assert (
        ProfileField.TARGET_COUNTRY
        in result.unknown_critical_fields
    )