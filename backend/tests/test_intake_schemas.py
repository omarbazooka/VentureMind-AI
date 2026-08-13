import pytest
from pydantic import ValidationError

from app.schemas.intake import (
    IntakeExtraction,
    IntakeProvenance,
    ProfileField,
    ProfileFieldUpdate,
    ProfileValueKind,
)


def test_intake_extraction_accepts_multiple_facts():
    extraction = IntakeExtraction(
        updates=[
            ProfileFieldUpdate(
                field=ProfileField.TARGET_CITY,
                value="Cairo",
                provenance=IntakeProvenance.USER,
                confidence=0.99,
            ),
            ProfileFieldUpdate(
                field=ProfileField.BUDGET,
                value=300000,
                provenance=IntakeProvenance.USER,
                confidence=0.98,
            ),
        ]
    )

    assert len(extraction.updates) == 2

    assert (
        extraction.updates[0].field
        == ProfileField.TARGET_CITY
    )

    assert (
        extraction.updates[1].value
        == 300000
    )


def test_intake_extraction_supports_user_assumption():
    extraction = IntakeExtraction(
        updates=[
            ProfileFieldUpdate(
                field=ProfileField.BUDGET,
                value=300000,
                provenance=IntakeProvenance.USER,
                value_kind=ProfileValueKind.ASSUMPTION,
                confidence=0.95,
            )
        ]
    )

    assert (
        extraction.updates[0].value_kind
        == ProfileValueKind.ASSUMPTION
    )


def test_intake_extraction_rejects_duplicate_fields():
    with pytest.raises(
        ValidationError,
        match="only be updated once",
    ):
        IntakeExtraction(
            updates=[
                ProfileFieldUpdate(
                    field=ProfileField.BUDGET,
                    value=300000,
                    provenance=IntakeProvenance.USER,
                    confidence=0.95,
                ),
                ProfileFieldUpdate(
                    field=ProfileField.BUDGET,
                    value=500000,
                    provenance=IntakeProvenance.USER,
                    confidence=0.95,
                ),
            ]
        )


def test_field_cannot_be_updated_and_unknown():
    with pytest.raises(
        ValidationError,
        match="both updated and unknown",
    ):
        IntakeExtraction(
            updates=[
                ProfileFieldUpdate(
                    field=ProfileField.BUDGET,
                    value=300000,
                    provenance=IntakeProvenance.USER,
                    confidence=0.95,
                )
            ],
            unknown_fields=[
                ProfileField.BUDGET,
            ],
        )