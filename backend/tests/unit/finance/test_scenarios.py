from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.finance.scenarios import (
    FinanceScenarioError,
    calculate_financial_scenarios,
)
from app.schemas.finance import (
    FinancialAssumption,
    FinancialAssumptionProvenance,
    FinancialAssumptionSet,
    FinancialInputName,
    FinancialMetricName,
    FinancialPeriod,
    FinancialScenarioInputs,
    FinancialScenarioKind,
)


def make_assumptions(
    *,
    scenario: FinancialScenarioKind,
    price: str,
    volume: str,
    variable_cost: str,
    fixed_costs: str = "10000",
    currency: str = "EGP",
    period: FinancialPeriod = (
        FinancialPeriod.MONTHLY
    ),
    unit_label: str = "customer",
    starting_cash: (
        str | None
    ) = None,
) -> FinancialAssumptionSet:
    cash = None

    if starting_cash is not None:
        cash = FinancialAssumption(
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
            currency=currency,
            rationale="Available cash.",
            profile_fields=[
                "starting_cash"
            ],
        )

    return FinancialAssumptionSet(
        scenario=scenario,

        selling_price_per_unit=(
            FinancialAssumption(
                input_name=(
                    FinancialInputName
                    .SELLING_PRICE_PER_UNIT
                ),
                value=Decimal(price),
                provenance=(
                    FinancialAssumptionProvenance
                    .AI_ASSUMPTION
                ),
                currency=currency,
                unit_label=unit_label,
                rationale=(
                    "Scenario selling "
                    "price assumption."
                ),
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
                unit_label=unit_label,
                period=period,
                rationale=(
                    "Scenario volume "
                    "assumption."
                ),
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
                currency=currency,
                unit_label=unit_label,
                rationale=(
                    "Scenario variable "
                    "cost assumption."
                ),
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
                    .AI_ASSUMPTION
                ),
                currency=currency,
                period=period,
                rationale=(
                    "Scenario fixed-cost "
                    "assumption."
                ),
            )
        ),

        starting_cash=cash,
    )


def make_inputs(
) -> FinancialScenarioInputs:
    return FinancialScenarioInputs(
        base=make_assumptions(
            scenario=(
                FinancialScenarioKind.BASE
            ),
            price="250",
            volume="100",
            variable_cost="50",
        ),

        upside=make_assumptions(
            scenario=(
                FinancialScenarioKind.UPSIDE
            ),
            price="300",
            volume="120",
            variable_cost="45",
        ),

        downside=make_assumptions(
            scenario=(
                FinancialScenarioKind.DOWNSIDE
            ),
            price="200",
            volume="80",
            variable_cost="60",
        ),
    )


def comparison_by_name(
    result,
    metric_name,
):
    return next(
        comparison
        for comparison
        in result.comparisons
        if (
            comparison.metric_name
            == metric_name
        )
    )


def test_calculates_three_financial_scenarios():
    result = (
        calculate_financial_scenarios(
            make_inputs()
        )
    )

    assert (
        result.base.scenario
        == FinancialScenarioKind.BASE
    )

    assert (
        result.upside.scenario
        == FinancialScenarioKind.UPSIDE
    )

    assert (
        result.downside.scenario
        == FinancialScenarioKind.DOWNSIDE
    )

    revenue = comparison_by_name(
        result,
        FinancialMetricName.REVENUE,
    )

    assert (
        revenue.base_value
        == Decimal("25000")
    )

    assert (
        revenue.upside_value
        == Decimal("36000")
    )

    assert (
        revenue.downside_value
        == Decimal("16000")
    )

    assert (
        revenue.upside_delta_from_base
        == Decimal("11000")
    )

    assert (
        revenue.downside_delta_from_base
        == Decimal("-9000")
    )


def test_compares_operating_result():
    result = (
        calculate_financial_scenarios(
            make_inputs()
        )
    )

    operating_result = (
        comparison_by_name(
            result,
            FinancialMetricName
            .OPERATING_RESULT,
        )
    )

    assert (
        operating_result.base_value
        == Decimal("10000")
    )

    assert (
        operating_result.upside_value
        == Decimal("20600")
    )

    assert (
        operating_result.downside_value
        == Decimal("1200")
    )

    assert (
        operating_result
        .upside_delta_from_base
        == Decimal("10600")
    )

    assert (
        operating_result
        .downside_delta_from_base
        == Decimal("-8800")
    )


def test_rejects_mislabeled_scenario_inputs():
    with pytest.raises(
        ValidationError
    ):
        FinancialScenarioInputs(
            base=make_assumptions(
                scenario=(
                    FinancialScenarioKind
                    .UPSIDE
                ),
                price="250",
                volume="100",
                variable_cost="50",
            ),

            upside=make_assumptions(
                scenario=(
                    FinancialScenarioKind
                    .UPSIDE
                ),
                price="300",
                volume="120",
                variable_cost="45",
            ),

            downside=make_assumptions(
                scenario=(
                    FinancialScenarioKind
                    .DOWNSIDE
                ),
                price="200",
                volume="80",
                variable_cost="60",
            ),
        )


def test_rejects_cross_scenario_currency_mismatch():
    inputs = FinancialScenarioInputs(
        base=make_assumptions(
            scenario=(
                FinancialScenarioKind.BASE
            ),
            price="250",
            volume="100",
            variable_cost="50",
        ),

        upside=make_assumptions(
            scenario=(
                FinancialScenarioKind.UPSIDE
            ),
            price="300",
            volume="120",
            variable_cost="45",
            currency="USD",
        ),

        downside=make_assumptions(
            scenario=(
                FinancialScenarioKind.DOWNSIDE
            ),
            price="200",
            volume="80",
            variable_cost="60",
        ),
    )

    with pytest.raises(
        FinanceScenarioError
    ):
        calculate_financial_scenarios(
            inputs
        )


def test_rejects_cross_scenario_period_mismatch():
    inputs = FinancialScenarioInputs(
        base=make_assumptions(
            scenario=(
                FinancialScenarioKind.BASE
            ),
            price="250",
            volume="100",
            variable_cost="50",
        ),

        upside=make_assumptions(
            scenario=(
                FinancialScenarioKind.UPSIDE
            ),
            price="300",
            volume="1440",
            variable_cost="45",
            period=(
                FinancialPeriod.ANNUAL
            ),
        ),

        downside=make_assumptions(
            scenario=(
                FinancialScenarioKind.DOWNSIDE
            ),
            price="200",
            volume="80",
            variable_cost="60",
        ),
    )

    with pytest.raises(
        FinanceScenarioError
    ):
        calculate_financial_scenarios(
            inputs
        )


def test_conditional_metric_can_be_missing_in_some_scenarios():
    inputs = FinancialScenarioInputs(
        base=make_assumptions(
            scenario=(
                FinancialScenarioKind.BASE
            ),
            price="250",
            volume="100",
            variable_cost="50",
            starting_cash="10000",
        ),

        upside=make_assumptions(
            scenario=(
                FinancialScenarioKind.UPSIDE
            ),
            price="300",
            volume="120",
            variable_cost="45",
            starting_cash="10000",
        ),

        downside=make_assumptions(
            scenario=(
                FinancialScenarioKind.DOWNSIDE
            ),
            price="100",
            volume="50",
            variable_cost="40",
            fixed_costs="5000",
            starting_cash="10000",
        ),
    )

    result = (
        calculate_financial_scenarios(
            inputs
        )
    )

    runway = comparison_by_name(
        result,
        FinancialMetricName
        .RUNWAY_PERIODS,
    )

    assert runway.base_value is None
    assert runway.upside_value is None

    assert (
        runway.downside_value
        == Decimal("5")
    )

    assert (
        runway.downside_delta_from_base
        is None
    )

    assert any(
        "RUNWAY_PERIODS"
        in limitation
        for limitation
        in result.limitations
    )