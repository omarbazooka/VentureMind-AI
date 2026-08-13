from typing import Any

from app.schemas.intake import (
    ProfileField,
    ProfileFieldUpdate,
)

from app.schemas.intake import (
    ProfileConflict,
    ProfileField,
    ProfileFieldUpdate,
    ProfileMergePlan,
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
                f"{field.value} cannot contain "
                "empty items"
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
                f"{field.value} must be text "
                "or a list of text values"
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
                f"{field.value} must be "
                "a boolean or text"
            )

    else:
        raise ProfileValueValidationError(
            f"No validation rule exists for "
            f"{field.value}"
        )

    return update.model_copy(
        update={
            "value": normalized_value,
        }
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
        # Strings
        if isinstance(
        current_value,
        str,
        ) and isinstance(
            proposed_value,
            str,
        ):
            return (
                current_value.strip().casefold()
                == proposed_value.strip().casefold() # better than lower()
            )

        # handling Numbers like 1 or 0 
        if isinstance(
        current_value,
        bool,
        ) or isinstance(
            proposed_value,
            bool,
        ):
            return (
                isinstance(current_value, bool)
                and isinstance(proposed_value, bool)
                and current_value == proposed_value
            )

        # Numbers
        if (
            isinstance(current_value, (int, float))
            and isinstance(proposed_value, (int, float))
        ):
            return current_value == proposed_value

        # Lists
        if (
            isinstance(current_value, list)
            and isinstance(proposed_value, list)
            and all(
                isinstance(item, str)
                for item in current_value
            )
            and all(
                isinstance(item, str)
                for item in proposed_value
            )
        ):
            current_normalized = sorted(
                item.strip().casefold()
                for item in current_value
            )

            proposed_normalized = sorted(
                item.strip().casefold()
                for item in proposed_value
            )

            return (
                current_normalized
                == proposed_normalized
            )

        return (
            type(current_value)
            is type(proposed_value)
            and current_value == proposed_value
        )

def plan_profile_merge(
    *,
    current_data: dict[str, Any],
    updates: list[ProfileFieldUpdate],
) -> ProfileMergePlan:

    validated_updates = validate_profile_updates(
        updates
    )
    candidate_data = dict(current_data)

    accepted_updates: list[
        ProfileFieldUpdate
    ] = []

    conflicts: list[
        ProfileConflict
    ] = []

    unchanged_fields: list[
        ProfileField
    ] = []


    for update in validated_updates:
        key = update.field.value
        # Accepting the Change
        if key not in current_data:
            accepted_updates.append(update)
            candidate_data[key] = update.value
            continue

        current_value = current_data[key]

        # Un Changing
        if _values_equivalent(
            current_value,
            update.value,
        ):
            unchanged_fields.append(
                update.field
            )
            continue

        # Conflict
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