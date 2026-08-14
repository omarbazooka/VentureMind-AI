from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.idea_profile import IdeaProfile
from app.schemas.intake import (
    ProfileConflict,
    ProfileField,
    ProfileFieldMetadata,
    ProfileFieldUpdate,
    ProfileMergePlan,
    IntakeProvenance,
    ProfileReadinessResult,
    ProfileReadinessStatus, 
    ClarificationTarget,
)


class ProfileValueValidationError(ValueError):
    pass


TEXT_FIELDS = {
    ProfileField.IDEA_NAME,
    ProfileField.IDEA_DESCRIPTION,
    ProfileField.PROBLEM,
    ProfileField.PROPOSED_SOLUTION,
    ProfileField.INDUSTRY,
    ProfileField.BUSINESS_TYPE,
    ProfileField.CUSTOMER_TYPE,
    ProfileField.TARGET_COUNTRY,
    ProfileField.TARGET_CITY,
    ProfileField.CURRENCY,
    ProfileField.REVENUE_MODEL,
    ProfileField.FOUNDER_EXPERIENCE,
    ProfileField.LAUNCH_TIMELINE,
    ProfileField.CURRENT_STAGE,
    ProfileField.USER_GOAL,
}

TEXT_OR_LIST_FIELDS = {
    ProfileField.TARGET_CUSTOMERS,
    ProfileField.KNOWN_COMPETITORS,
}

BOOLEAN_OR_TEXT_FIELDS = {
    ProfileField.EXISTING_TEAM,
}

NUMBER_FIELDS = {
    ProfileField.BUDGET,
}

DIRECT_CRITICAL_FIELDS = (
    ProfileField.TARGET_CUSTOMERS,
    ProfileField.TARGET_COUNTRY,
)


CORE_IDEA_FIELDS = (
    ProfileField.IDEA_DESCRIPTION,
    ProfileField.PROBLEM,
    ProfileField.PROPOSED_SOLUTION,
)


OPTIONAL_PROFILE_FIELDS = (
    ProfileField.IDEA_NAME,
    ProfileField.INDUSTRY,
    ProfileField.BUSINESS_TYPE,
    ProfileField.CUSTOMER_TYPE,
    ProfileField.TARGET_CITY,
    ProfileField.BUDGET,
    ProfileField.CURRENCY,
    ProfileField.REVENUE_MODEL,
    ProfileField.FOUNDER_EXPERIENCE,
    ProfileField.EXISTING_TEAM,
    ProfileField.LAUNCH_TIMELINE,
    ProfileField.KNOWN_COMPETITORS,
    ProfileField.CURRENT_STAGE,
    ProfileField.USER_GOAL,
)


# CLARIFICATION_QUESTIONS = {
#     ProfileField.IDEA_DESCRIPTION: (
#         "Describe the business idea in one "
#         "or two sentences. What are you "
#         "offering and what problem does it solve?"
#     ),
#     ProfileField.PROBLEM: (
#         "What main problem are you trying "
#         "to solve for the customer?"
#     ),
#     ProfileField.PROPOSED_SOLUTION: (
#         "How will your product or service "
#         "solve that problem?"
#     ),
#     ProfileField.TARGET_CUSTOMERS: (
#         "Who are the main customers you "
#         "expect to use or pay for this?"
#     ),
#     ProfileField.TARGET_COUNTRY: (
#         "Which country do you want to "
#         "target first?"
#     ),
# }

# ASSUMPTION_QUESTIONS = {
#     ProfileField.IDEA_DESCRIPTION: (
#         "If the idea is still unclear, what "
#         "working description should we use "
#         "for now?"
#     ),
#     ProfileField.PROBLEM: (
#         "If you're not certain yet, what "
#         "customer problem should we treat "
#         "as the current working assumption?"
#     ),
#     ProfileField.PROPOSED_SOLUTION: (
#         "If the solution is not final yet, "
#         "what approach should we treat as "
#         "the working assumption?"
#     ),
#     ProfileField.TARGET_CUSTOMERS: (
#         "If you're not sure yet, which "
#         "customer group should we use as "
#         "a working assumption?"
#     ),
#     ProfileField.TARGET_COUNTRY: (
#         "If the market is not decided yet, "
#         "which country should we use as a "
#         "working assumption for the analysis?"
#     ),
# }

def _normalize_text(
    *,
    field: ProfileField,
    value: str,
) -> str:
    cleaned = value.strip()

    if not cleaned:
        raise ProfileValueValidationError(
            f"{field.value} cannot be empty"
        )

    return cleaned


def _normalize_text_list(
    *,
    field: ProfileField,
    value: list[str],
) -> list[str]:
    if not value:
        raise ProfileValueValidationError(
            f"{field.value} cannot be an empty list"
        )

    cleaned_items: list[str] = []

    for item in value:
        cleaned_item = item.strip()

        if not cleaned_item:
            raise ProfileValueValidationError(
                f"{field.value} cannot contain empty items"
            )

        cleaned_items.append(cleaned_item)

    return cleaned_items


def validate_and_normalize_update(
    update: ProfileFieldUpdate,
) -> ProfileFieldUpdate:
    field = update.field
    value = update.value

    if field in TEXT_FIELDS:
        if not isinstance(value, str):
            raise ProfileValueValidationError(
                f"{field.value} must be text"
            )

        normalized_value = _normalize_text(
            field=field,
            value=value,
        )

    elif field in TEXT_OR_LIST_FIELDS:
        if isinstance(value, str):
            normalized_value = _normalize_text(
                field=field,
                value=value,
            )
        elif isinstance(value, list):
            normalized_value = _normalize_text_list(
                field=field,
                value=value,
            )
        else:
            raise ProfileValueValidationError(
                f"{field.value} must be text or a list of text values"
            )

    elif field in NUMBER_FIELDS:
        if isinstance(value, bool) or not isinstance(
            value,
            (int, float),
        ):
            raise ProfileValueValidationError(
                f"{field.value} must be numeric"
            )

        if value < 0:
            raise ProfileValueValidationError(
                f"{field.value} cannot be negative"
            )

        normalized_value = value

    elif field in BOOLEAN_OR_TEXT_FIELDS:
        if isinstance(value, bool):
            normalized_value = value
        elif isinstance(value, str):
            normalized_value = _normalize_text(
                field=field,
                value=value,
            )
        else:
            raise ProfileValueValidationError(
                f"{field.value} must be a boolean or text"
            )

    else:
        raise ProfileValueValidationError(
            f"No validation rule exists for {field.value}"
        )

    return update.model_copy(
        update={"value": normalized_value}
    )


def validate_profile_updates(
    updates: list[ProfileFieldUpdate],
) -> list[ProfileFieldUpdate]:
    return [
        validate_and_normalize_update(update)
        for update in updates
    ]


def _values_equivalent(
    current_value: Any,
    proposed_value: Any,
) -> bool:
    if isinstance(current_value, str) and isinstance(
        proposed_value,
        str,
    ):
        return (
            current_value.strip().casefold()
            == proposed_value.strip().casefold()
        )

    if isinstance(current_value, bool) or isinstance(
        proposed_value,
        bool,
    ):
        return (
            isinstance(current_value, bool)
            and isinstance(proposed_value, bool)
            and current_value == proposed_value
        )

    if isinstance(current_value, (int, float)) and isinstance(
        proposed_value,
        (int, float),
    ):
        return current_value == proposed_value

    if (
        isinstance(current_value, list)
        and isinstance(proposed_value, list)
        and all(isinstance(item, str) for item in current_value)
        and all(isinstance(item, str) for item in proposed_value)
    ):
        current_normalized = sorted(
            item.strip().casefold()
            for item in current_value
        )
        proposed_normalized = sorted(
            item.strip().casefold()
            for item in proposed_value
        )
        return current_normalized == proposed_normalized

    return (
        type(current_value) is type(proposed_value)
        and current_value == proposed_value
    )


def plan_profile_merge(
    *,
    current_data: dict[str, Any],
    updates: list[ProfileFieldUpdate],
) -> ProfileMergePlan:
    validated_updates = validate_profile_updates(updates)
    candidate_data = dict(current_data)

    accepted_updates: list[ProfileFieldUpdate] = []
    conflicts: list[ProfileConflict] = []
    unchanged_fields: list[ProfileField] = []

    for update in validated_updates:
        key = update.field.value

        if key not in current_data:
            accepted_updates.append(update)
            candidate_data[key] = update.value
            continue

        current_value = current_data[key]

        if _values_equivalent(
            current_value,
            update.value,
        ):
            unchanged_fields.append(update.field)
            continue

        conflicts.append(
            ProfileConflict(
                field=update.field,
                current_value=current_value,
                proposed_value=update.value,
            )
        )

    return ProfileMergePlan(
        accepted_updates=accepted_updates,
        conflicts=conflicts,
        unchanged_fields=unchanged_fields,
        candidate_profile_data=candidate_data,
    )


def persist_profile_merge_plan(
    *,
    db: Session,
    idea_id: UUID,
    current_profile: IdeaProfile,
    merge_plan: ProfileMergePlan,
    source_message_id: UUID | None = None,
) -> IdeaProfile:
    if current_profile.idea_id != idea_id:
        raise ValueError(
            "current_profile does not belong to idea_id"
        )

    if not merge_plan.accepted_updates:
        return current_profile

    next_metadata = dict(
        current_profile.profile_metadata or {}
    )
    accepted_field_names: set[str] = set()

    for update in merge_plan.accepted_updates:
        field_name = update.field.value
        accepted_field_names.add(field_name)

        metadata = ProfileFieldMetadata(
            provenance=update.provenance,
            value_kind=update.value_kind,
            confidence=update.confidence,
            source_message_id=source_message_id,
        )

        next_metadata[field_name] = metadata.model_dump(
            mode="json"
        )

    next_unknown_fields = [
        field_name
        for field_name in (current_profile.unknown_fields or [])
        if field_name not in accepted_field_names
    ]

    readiness_result = (
        evaluate_profile_readiness(
            profile_data=(
                merge_plan.candidate_profile_data
            ),
            profile_metadata=next_metadata,
            unknown_fields=next_unknown_fields,
        )
    )

    new_profile = IdeaProfile(
        idea_id=idea_id,
        version=current_profile.version + 1,
        readiness=(
            readiness_result.readiness.value
        ),
        profile_data=dict(
            merge_plan.candidate_profile_data
        ),
        profile_metadata=next_metadata,
        unknown_fields=next_unknown_fields,
    )

    db.add(new_profile)
    db.flush()

    return new_profile


def _has_user_grounded_value(
    *,
    field: ProfileField,
    profile_data: dict[str, Any],
    profile_metadata: dict[
        str,
        dict[str, Any],
    ],
    unknown_field_names: set[str],
) -> bool:
    field_name = field.value

    if field_name in unknown_field_names:
        return False

    if field_name not in profile_data:
        return False

    metadata = profile_metadata.get(
        field_name
    )

    if metadata is None:
        return False

    provenance = metadata.get(
        "provenance"
    )

    return provenance in {
        IntakeProvenance.USER,
        IntakeProvenance.USER.value,
    }


def evaluate_profile_readiness(
    *,
    profile_data: dict[str, Any],
    profile_metadata: dict[
        str,
        dict[str, Any],
    ],
    unknown_fields: list[str],
) -> ProfileReadinessResult:
    unknown_field_names = set(
        unknown_fields
    )

    missing_critical_fields: list[
        ProfileField
    ] = []

    unknown_critical_fields: list[
        ProfileField
    ] = []

    has_idea_description = (
        _has_user_grounded_value(
            field=ProfileField.IDEA_DESCRIPTION,
            profile_data=profile_data,
            profile_metadata=profile_metadata,
            unknown_field_names=unknown_field_names,
        )
    )

    has_problem = (
        _has_user_grounded_value(
            field=ProfileField.PROBLEM,
            profile_data=profile_data,
            profile_metadata=profile_metadata,
            unknown_field_names=unknown_field_names,
        )
    )

    has_solution = (
        _has_user_grounded_value(
            field=ProfileField.PROPOSED_SOLUTION,
            profile_data=profile_data,
            profile_metadata=profile_metadata,
            unknown_field_names=unknown_field_names,
        )
    )

    core_idea_ready = (
        has_idea_description
        or (
            has_problem
            and has_solution
        )
    )

    if not core_idea_ready:
        missing_critical_fields.append(
            ProfileField.IDEA_DESCRIPTION
        )

        for field in CORE_IDEA_FIELDS:
            if field.value in unknown_field_names:
                unknown_critical_fields.append(
                    field
                )

    for field in DIRECT_CRITICAL_FIELDS:
        if _has_user_grounded_value(
            field=field,
            profile_data=profile_data,
            profile_metadata=profile_metadata,
            unknown_field_names=unknown_field_names,
        ):
            continue

        missing_critical_fields.append(
            field
        )

        if field.value in unknown_field_names:
            unknown_critical_fields.append(
                field
            )

    missing_optional_fields = [
        field
        for field in OPTIONAL_PROFILE_FIELDS
        if (
            field.value
            not in profile_data
            and field.value
            not in unknown_field_names
        )
    ]

    readiness = (
        ProfileReadinessStatus.READY_FOR_ANALYSIS
        if not missing_critical_fields
        else ProfileReadinessStatus.NOT_READY
    )

    return ProfileReadinessResult(
        readiness=readiness,
        missing_critical_fields=(
            missing_critical_fields
        ),
        missing_optional_fields=(
            missing_optional_fields
        ),
        unknown_critical_fields=(
            unknown_critical_fields
        ),
    )
def select_next_clarification_target(
    *,
    readiness_result: ProfileReadinessResult,
    profile_data: dict[str, Any],
    profile_metadata: dict[
        str,
        dict[str, Any],
    ],
    unknown_fields: list[str],
) -> ClarificationTarget | None:
    if (
        readiness_result.readiness
        == ProfileReadinessStatus.READY_FOR_ANALYSIS
    ):
        return None

    unknown_field_names = set(
        unknown_fields
    )

    missing_critical_fields = set(
        readiness_result.missing_critical_fields
    )

    if (
        ProfileField.IDEA_DESCRIPTION
        in missing_critical_fields
    ):
        has_problem = _has_user_grounded_value(
            field=ProfileField.PROBLEM,
            profile_data=profile_data,
            profile_metadata=profile_metadata,
            unknown_field_names=unknown_field_names,
        )

        has_solution = _has_user_grounded_value(
            field=ProfileField.PROPOSED_SOLUTION,
            profile_data=profile_data,
            profile_metadata=profile_metadata,
            unknown_field_names=unknown_field_names,
        )

        if (
            has_problem
            and not has_solution
            and (
                ProfileField.PROPOSED_SOLUTION.value
                not in unknown_field_names
            )
        ):
            return ClarificationTarget(
                field=ProfileField.PROPOSED_SOLUTION,
            )

        if (
            has_solution
            and not has_problem
            and (
                ProfileField.PROBLEM.value
                not in unknown_field_names
            )
        ):
            return ClarificationTarget(
                field=ProfileField.PROBLEM,
            )

        for field in CORE_IDEA_FIELDS:
            if field.value in unknown_field_names:
                continue

            if _has_user_grounded_value(
                field=field,
                profile_data=profile_data,
                profile_metadata=profile_metadata,
                unknown_field_names=unknown_field_names,
            ):
                continue

            return ClarificationTarget(
                field=field,
            )

    for field in DIRECT_CRITICAL_FIELDS:
        if field not in missing_critical_fields:
            continue

        if field.value in unknown_field_names:
            continue

        return ClarificationTarget(
            field=field,
        )

    for field in (
        ProfileField.IDEA_DESCRIPTION,
        ProfileField.PROBLEM,
        ProfileField.PROPOSED_SOLUTION,
        ProfileField.TARGET_CUSTOMERS,
        ProfileField.TARGET_COUNTRY,
    ):
        if (
            field
            in readiness_result.unknown_critical_fields
        ):
            return ClarificationTarget(
                field=field,
                is_assumption_prompt=True,
            )

    return None