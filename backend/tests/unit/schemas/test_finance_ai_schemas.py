from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.finance import (
    FinancialAssumptionProvenance,
    FinancialInputName,
)
from app.schemas.finance_ai import (
    FinancialAssumptionDraft,
)


def test_known_draft_requires_provenance():
    with pytest.raises(
        ValidationError
    ):
        FinancialAssumptionDraft(
            input_name=(
                FinancialInputName
                .STARTING_CASH
            ),
            value=Decimal("100000"),
            currency="EGP",
            rationale="Available cash.",
        )


def test_unknown_draft_cannot_claim_provenance():
    with pytest.raises(
        ValidationError
    ):
        FinancialAssumptionDraft(
            input_name=(
                FinancialInputName
                .STARTING_CASH
            ),
            value=None,
            provenance=(
                FinancialAssumptionProvenance
                .USER
            ),
            rationale=(
                "Starting cash is unknown."
            ),
        )


def test_user_draft_requires_profile_fields():
    with pytest.raises(
        ValidationError
    ):
        FinancialAssumptionDraft(
            input_name=(
                FinancialInputName
                .STARTING_CASH
            ),
            value=Decimal("100000"),
            provenance=(
                FinancialAssumptionProvenance
                .USER
            ),
            currency="EGP",
            rationale="Available cash.",
        )


def test_web_draft_requires_source_ids():
    with pytest.raises(
        ValidationError
    ):
        FinancialAssumptionDraft(
            input_name=(
                FinancialInputName
                .VARIABLE_COST_PER_UNIT
            ),
            value=Decimal("30"),
            provenance=(
                FinancialAssumptionProvenance
                .WEB
            ),
            currency="EGP",
            unit_label="customer",
            rationale="Observed cost.",
            supporting_stages=[
                AnalysisStage.MARKET_RESEARCH
            ],
        )


def test_ai_assumption_cannot_claim_lineage():
    with pytest.raises(
        ValidationError
    ):
        FinancialAssumptionDraft(
            input_name=(
                FinancialInputName
                .SELLING_PRICE_PER_UNIT
            ),
            value=Decimal("250"),
            provenance=(
                FinancialAssumptionProvenance
                .AI_ASSUMPTION
            ),
            currency="EGP",
            unit_label="customer",
            rationale="Scenario price.",
            profile_fields=[
                "selling_price"
            ],
        )