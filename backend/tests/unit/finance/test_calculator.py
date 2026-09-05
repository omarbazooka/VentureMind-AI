from decimal import Decimal

import pytest

from app.finance.calculator import (
    FinanceCalculationError,
    calculate_financial_scenario,
)
from app.schemas.finance import (
    FinancialAssumption,
    FinancialAssumptionProvenance,
    FinancialAssumptionSet,
    FinancialInputName,
    FinancialMetricName,
    FinancialPeriod,
    FinancialScenarioKind,
)


def make_assumptions(
    *,
    price: str = "250",
    volume: str = "100",
    variable_cost: str = "50",
    fixed_costs: str = "10000",
    fixed_period: (
        FinancialPeriod
    ) = FinancialPeriod.MONTHLY,
    starting_cash: str | None = None,
    variable_currency: str = "EGP",
) -> FinancialAssumptionSet:
    cash_assumption = None

    if starting_cash is not None:
        cash_assumption = (
            FinancialAssumption(
                input_name=(
                    FinancialInputName
                    .STARTING_CASH
                ),
                value=Decimal(
                    starting_cash
                ),
                provenance=(
                    FinancialAssumptionProvenance
                    .USER
                ),
                currency="EGP",
                rationale="Available cash.",
                profile_fields=[
                    "starting_cash"
                ],
            )
        )

    return FinancialAssumptionSet(
        scenario=(
            FinancialScenarioKind.BASE
        ),
        selling_price_per_unit=(
            FinancialAssumption(
                input_name=(
                    FinancialInputName
                    .SELLING_PRICE_PER_UNIT
                ),
                value=Decimal(price),
                provenance=(
                    FinancialAssumptionProvenance
                    .USER
                ),
                currency="EGP",
                unit_label="customer",
                rationale="Selling price.",
                profile_fields=[
                    "selling_price"
                ],
            )
        ),
        sales_volume=(
            FinancialAssumption(
                input_name=(
                    FinancialInputName
                    .SALES_VOLUME
                ),
                value=Decimal(volume),
                provenance=(
                    FinancialAssumptionProvenance
                    .AI_ASSUMPTION
                ),
                unit_label="customer",
                period=(
                    FinancialPeriod.MONTHLY
                ),
                rationale="Monthly volume.",
            )
        ),
        variable_cost_per_unit=(
            FinancialAssumption(
                input_name=(
                    FinancialInputName
                    .VARIABLE_COST_PER_UNIT
                ),
                value=Decimal(
                    variable_cost
                ),
                provenance=(
                    FinancialAssumptionProvenance
                    .AI_ASSUMPTION
                ),
                currency=(
                    variable_currency
                ),
                unit_label="customer",
                rationale="Variable cost.",
            )
        ),
        fixed_costs=(
            FinancialAssumption(
                input_name=(
                    FinancialInputName
                    .FIXED_COSTS
                ),
                value=Decimal(
                    fixed_costs
                ),
                provenance=(
                    FinancialAssumptionProvenance
                    .USER
                ),
                currency="EGP",
                period=fixed_period,
                rationale="Fixed costs.",
                profile_fields=[
                    "fixed_costs"
                ],
            )
        ),
        starting_cash=(
            cash_assumption
        ),
    )


def metric_by_name(
    result,
    metric_name,
):
    return next(
        metric
        for metric in result.metrics
        if (
            metric.metric_name
            == metric_name
        )
    )


def test_calculates_core_monthly_metrics():
    result = (
        calculate_financial_scenario(
            make_assumptions()
        )
    )

    assert (
        metric_by_name(
            result,
            FinancialMetricName.REVENUE,
        ).value
        == Decimal("25000")
    )

    assert (
        metric_by_name(
            result,
            FinancialMetricName
            .VARIABLE_COSTS,
        ).value
        == Decimal("5000")
    )

    assert (
        metric_by_name(
            result,
            FinancialMetricName
            .CONTRIBUTION_PROFIT,
        ).value
        == Decimal("20000")
    )

    assert (
        metric_by_name(
            result,
            FinancialMetricName
            .CONTRIBUTION_MARGIN_PERCENT,
        ).value
        == Decimal("80")
    )

    assert (
        metric_by_name(
            result,
            FinancialMetricName
            .OPERATING_RESULT,
        ).value
        == Decimal("10000")
    )

    assert (
        metric_by_name(
            result,
            FinancialMetricName
            .BREAK_EVEN_UNITS,
        ).value
        == Decimal("50")
    )


def test_normalizes_annual_fixed_costs_to_monthly():
    result = (
        calculate_financial_scenario(
            make_assumptions(
                fixed_costs="120000",
                fixed_period=(
                    FinancialPeriod.ANNUAL
                ),
            )
        )
    )

    operating_result = metric_by_name(
        result,
        FinancialMetricName
        .OPERATING_RESULT,
    )

    assert (
        operating_result.value
        == Decimal("10000")
    )

    assert (
        operating_result.period
        == FinancialPeriod.MONTHLY
    )


def test_calculates_runway_when_business_is_burning_cash():
    result = (
        calculate_financial_scenario(
            make_assumptions(
                price="100",
                volume="50",
                variable_cost="40",
                fixed_costs="5000",
                starting_cash="10000",
            )
        )
    )

    assert (
        metric_by_name(
            result,
            FinancialMetricName
            .OPERATING_RESULT,
        ).value
        == Decimal("-2000")
    )

    runway = metric_by_name(
        result,
        FinancialMetricName
        .RUNWAY_PERIODS,
    )

    assert runway.value == Decimal("5")

    assert runway.unit == "months"


def test_profitable_business_does_not_emit_runway():
    result = (
        calculate_financial_scenario(
            make_assumptions(
                starting_cash="100000"
            )
        )
    )

    metric_names = {
        metric.metric_name
        for metric in result.metrics
    }

    assert (
        FinancialMetricName
        .RUNWAY_PERIODS
        not in metric_names
    )

    assert any(
        "non-negative"
        in limitation
        for limitation
        in result.limitations
    )


def test_non_positive_contribution_does_not_emit_break_even():
    result = (
        calculate_financial_scenario(
            make_assumptions(
                price="50",
                variable_cost="60",
            )
        )
    )

    metric_names = {
        metric.metric_name
        for metric in result.metrics
    }

    assert (
        FinancialMetricName
        .BREAK_EVEN_UNITS
        not in metric_names
    )

    assert any(
        "not positive"
        in limitation
        for limitation
        in result.limitations
    )


def test_zero_revenue_does_not_emit_margin():
    result = (
        calculate_financial_scenario(
            make_assumptions(
                price="0",
                variable_cost="0",
            )
        )
    )

    metric_names = {
        metric.metric_name
        for metric in result.metrics
    }

    assert (
        FinancialMetricName
        .CONTRIBUTION_MARGIN_PERCENT
        not in metric_names
    )

    assert any(
        "revenue is zero"
        in limitation
        for limitation
        in result.limitations
    )


def test_rejects_assumptions_that_are_not_ready():
    with pytest.raises(
        FinanceCalculationError
    ):
        calculate_financial_scenario(
            make_assumptions(
                variable_currency="USD"
            )
        )