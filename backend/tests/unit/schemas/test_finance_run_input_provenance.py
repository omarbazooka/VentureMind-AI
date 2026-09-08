from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.analysis import AnalysisStage
from app.schemas.finance import (
    FinancialAssumption,
    FinancialAssumptionProvenance,
    FinancialInputName,
)


def test_user_value_accepts_analysis_run_input_lineage():
    run_input_id = uuid4()

    assumption = FinancialAssumption(
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        value=Decimal("350"),
        provenance=(
            FinancialAssumptionProvenance.USER
        ),
        currency="EGP",
        unit_label="customer",
        rationale="User selected during analysis.",
        analysis_run_input_ids=[
            run_input_id
        ],
    )

    assert assumption.profile_fields == []
    assert assumption.analysis_run_input_ids == [
        run_input_id
    ]


def test_web_value_cannot_claim_analysis_run_input_lineage():
    with pytest.raises(ValidationError):
        FinancialAssumption(
            input_name=(
                FinancialInputName
                .SELLING_PRICE_PER_UNIT
            ),
            value=Decimal("350"),
            provenance=(
                FinancialAssumptionProvenance.WEB
            ),
            currency="EGP",
            unit_label="customer",
            rationale="Invalid mixed lineage.",
            analysis_run_input_ids=[uuid4()],
            supporting_stages=[
                AnalysisStage.COMPETITOR_INTELLIGENCE
            ],
            evidence_source_ids=["source-1"],
        )


def test_unknown_value_cannot_claim_run_input_lineage():
    with pytest.raises(ValidationError):
        FinancialAssumption(
            input_name=(
                FinancialInputName
                .SELLING_PRICE_PER_UNIT
            ),
            value=None,
            provenance=None,
            currency="EGP",
            unit_label="customer",
            rationale="Still unknown.",
            analysis_run_input_ids=[uuid4()],
        )
