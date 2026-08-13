from typing import Any

from app.schemas.intake import (
    ProfileField,
    ProfileFieldUpdate,
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


def build_candidate_profile_data(
    *,
    current_data: dict[str, Any],
    updates: list[ProfileFieldUpdate],
) -> dict[str, Any]:
    candidate_data = dict(current_data)

    for update in updates:
        validated_update = (
            validate_and_normalize_update(update)
        )

        candidate_data[
            validated_update.field.value
        ] = validated_update.value

    return candidate_data