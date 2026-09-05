import pytest
from pydantic import ValidationError

from app.schemas.finance import (
    FinancialAssumption,
    FinancialInputName,
)
from app.schemas.finance_ai import FinancialAssumptionDraft


def test_unknown_financial_value_can_omit_metadata():
    assumption = FinancialAssumption(
        input_name=FinancialInputName.SELLING_PRICE_PER_UNIT,
        value=None,
        provenance=None,
        rationale="Selling price is not known yet.",
    )

    assert assumption.value is None
    assert assumption.currency is None
    assert assumption.unit_label is None
    assert assumption.period is None


def test_unknown_draft_can_omit_financial_metadata():
    draft = FinancialAssumptionDraft(
        input_name=FinancialInputName.SELLING_PRICE_PER_UNIT,
        value=None,
        provenance=None,
        rationale="Selling price remains unknown.",
    )

    assert draft.value is None
    assert draft.currency is None
    assert draft.unit_label is None
    assert draft.period is None


def test_unknown_starting_cash_rejects_irrelevant_unit_label():
    with pytest.raises(ValidationError):
        FinancialAssumptionDraft(
            input_name=FinancialInputName.STARTING_CASH,
            value=None,
            provenance=None,
            unit_label="customer",
            rationale="Starting cash is unknown.",
        )
