from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.finance import (
    FinancialInputName,
    FinancialPeriod,
)
from app.schemas.finance_runtime import (
    FinanceInputRequest,
    FinanceUserAnswerMode,
    FinanceUserInputAnswer,
)


def test_request_can_leave_expected_metadata_unknown():
    request = FinanceInputRequest(
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        question=(
            "What price will you charge?"
        ),
    )

    assert request.currency is None
    assert request.unit_label is None


def test_request_normalizes_known_metadata():
    request = FinanceInputRequest(
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        question="  What price?  ",
        currency=" egp ",
        unit_label=" customer ",
    )

    assert request.question == "What price?"
    assert request.currency == "EGP"
    assert request.unit_label == "customer"


def test_request_rejects_irrelevant_unit_metadata():
    with pytest.raises(ValidationError):
        FinanceInputRequest(
            input_name=(
                FinancialInputName
                .STARTING_CASH
            ),
            question=(
                "How much cash is available?"
            ),
            currency="EGP",
            unit_label="customer",
        )


def test_selling_price_answer_requires_currency():
    with pytest.raises(ValidationError):
        FinanceUserInputAnswer(
            input_name=(
                FinancialInputName
                .SELLING_PRICE_PER_UNIT
            ),
            answer_mode=(
                FinanceUserAnswerMode.CUSTOM
            ),
            value=Decimal("250"),
            unit_label="customer",
        )


def test_selling_price_answer_requires_unit():
    with pytest.raises(ValidationError):
        FinanceUserInputAnswer(
            input_name=(
                FinancialInputName
                .SELLING_PRICE_PER_UNIT
            ),
            answer_mode=(
                FinanceUserAnswerMode.CUSTOM
            ),
            value=Decimal("250"),
            currency="EGP",
        )


def test_sales_volume_requires_unit_and_period():
    answer = FinanceUserInputAnswer(
        input_name=(
            FinancialInputName.SALES_VOLUME
        ),
        answer_mode=(
            FinanceUserAnswerMode.CUSTOM
        ),
        value=Decimal("100"),
        unit_label="customer",
        period=FinancialPeriod.MONTHLY,
    )

    assert answer.value == Decimal("100")
    assert (
        answer.period
        == FinancialPeriod.MONTHLY
    )


def test_sales_volume_rejects_currency():
    with pytest.raises(ValidationError):
        FinanceUserInputAnswer(
            input_name=(
                FinancialInputName
                .SALES_VOLUME
            ),
            answer_mode=(
                FinanceUserAnswerMode.CUSTOM
            ),
            value=Decimal("100"),
            currency="EGP",
            unit_label="customer",
            period=FinancialPeriod.MONTHLY,
        )


def test_fixed_cost_answer_requires_period():
    with pytest.raises(ValidationError):
        FinanceUserInputAnswer(
            input_name=(
                FinancialInputName.FIXED_COSTS
            ),
            answer_mode=(
                FinanceUserAnswerMode.CUSTOM
            ),
            value=Decimal("10000"),
            currency="EGP",
        )


def test_starting_cash_requires_only_currency():
    answer = FinanceUserInputAnswer(
        input_name=(
            FinancialInputName.STARTING_CASH
        ),
        answer_mode=(
            FinanceUserAnswerMode.CUSTOM
        ),
        value=Decimal("200000"),
        currency="egp",
    )

    assert answer.currency == "EGP"
    assert answer.unit_label is None
    assert answer.period is None


def test_starting_cash_rejects_period():
    with pytest.raises(ValidationError):
        FinanceUserInputAnswer(
            input_name=(
                FinancialInputName.STARTING_CASH
            ),
            answer_mode=(
                FinanceUserAnswerMode.CUSTOM
            ),
            value=Decimal("200000"),
            currency="EGP",
            period=FinancialPeriod.MONTHLY,
        )


def test_answer_rejects_negative_value():
    with pytest.raises(ValidationError):
        FinanceUserInputAnswer(
            input_name=(
                FinancialInputName
                .SELLING_PRICE_PER_UNIT
            ),
            answer_mode=(
                FinanceUserAnswerMode.CUSTOM
            ),
            value=Decimal("-1"),
            currency="EGP",
            unit_label="customer",
        )


def test_selected_option_answer_cannot_override_value():
    with pytest.raises(ValidationError):
        FinanceUserInputAnswer(
            input_name=(
                FinancialInputName
                .SELLING_PRICE_PER_UNIT
            ),
            answer_mode=(
                FinanceUserAnswerMode
                .SELECTED_OPTION
            ),
            selected_option_id=(
                "market_midpoint"
            ),
            value=Decimal("999999"),
            currency="EGP",
            unit_label="customer",
        )
