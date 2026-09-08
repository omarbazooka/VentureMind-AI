from decimal import Decimal

import pytest

from app.analytics.sensitivity import (
    DecisionSensitivityError,
    calculate_sensitivity_analysis,
)
from app.finance.calculator import (
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
    scenario: FinancialScenarioKind = FinancialScenarioKind.BASE,
    price: str = "250",
    volume: str = "100",
    variable_cost: str = "50",
    fixed_costs: str = "10000",
) -> FinancialAssumptionSet:
    return FinancialAssumptionSet(
        scenario=scenario,
        selling_price_per_unit=FinancialAssumption(
            input_name=(
                FinancialInputName.SELLING_PRICE_PER_UNIT
            ),
            value=Decimal(price),
            provenance=FinancialAssumptionProvenance.USER,
            currency="EGP",
            unit_label="customer",
            rationale="Selling price.",
            profile_fields=["selling_price"],
        ),
        sales_volume=FinancialAssumption(
            input_name=FinancialInputName.SALES_VOLUME,
            value=Decimal(volume),
            provenance=(
                FinancialAssumptionProvenance.AI_ASSUMPTION
            ),
            unit_label="customer",
            period=FinancialPeriod.MONTHLY,
            rationale="Monthly volume.",
        ),
        variable_cost_per_unit=FinancialAssumption(
            input_name=(
                FinancialInputName.VARIABLE_COST_PER_UNIT
            ),
            value=Decimal(variable_cost),
            provenance=(
                FinancialAssumptionProvenance.AI_ASSUMPTION
            ),
            currency="EGP",
            unit_label="customer",
            rationale="Variable cost.",
        ),
        fixed_costs=FinancialAssumption(
            input_name=FinancialInputName.FIXED_COSTS,
            value=Decimal(fixed_costs),
            provenance=FinancialAssumptionProvenance.USER,
            currency="EGP",
            period=FinancialPeriod.MONTHLY,
            rationale="Fixed costs.",
            profile_fields=["fixed_costs"],
        ),
    )


def item_by_input(result, input_name):
    return next(
        item
        for item in result.inputs
        if item.input_name == input_name
    )


def impact_by_metric(point, metric_name):
    return next(
        impact
        for impact in point.impacts
        if impact.metric_name == metric_name
    )


def test_ranks_inputs_by_operating_result_sensitivity():
    base_result = calculate_financial_scenario(
        make_assumptions()
    )

    result = calculate_sensitivity_analysis(base_result)

    price = item_by_input(
        result,
        FinancialInputName.SELLING_PRICE_PER_UNIT,
    )
    volume = item_by_input(
        result,
        FinancialInputName.SALES_VOLUME,
    )
    fixed = item_by_input(
        result,
        FinancialInputName.FIXED_COSTS,
    )
    variable = item_by_input(
        result,
        FinancialInputName.VARIABLE_COST_PER_UNIT,
    )

    assert price.rank == 1
    assert volume.rank == 2
    assert fixed.rank == 3
    assert variable.rank == 4
    assert price.max_abs_ranking_metric_change_percent == Decimal("25.00")
    assert volume.max_abs_ranking_metric_change_percent == Decimal("20.0")
    assert fixed.max_abs_ranking_metric_change_percent == Decimal("10.0")
    assert variable.max_abs_ranking_metric_change_percent == Decimal("5.00")


def test_sensitivity_preserves_direction_of_cost_changes():
    base_result = calculate_financial_scenario(
        make_assumptions()
    )

    result = calculate_sensitivity_analysis(base_result)
    variable = item_by_input(
        result,
        FinancialInputName.VARIABLE_COST_PER_UNIT,
    )

    decrease_impact = impact_by_metric(
        variable.decrease,
        FinancialMetricName.OPERATING_RESULT,
    )
    increase_impact = impact_by_metric(
        variable.increase,
        FinancialMetricName.OPERATING_RESULT,
    )

    assert decrease_impact.relative_change_percent == Decimal("5.00")
    assert increase_impact.relative_change_percent == Decimal("-5.00")


def test_zero_base_ranking_metric_keeps_impacts_but_skips_ranking():
    base_result = calculate_financial_scenario(
        make_assumptions(fixed_costs="20000")
    )

    result = calculate_sensitivity_analysis(base_result)

    assert all(item.rank is None for item in result.inputs)
    assert all(
        item.max_abs_ranking_metric_change_percent is None
        for item in result.inputs
    )
    assert any(
        "relative change is undefined" in limitation
        for limitation in result.limitations
    )


def test_missing_stressed_break_even_is_recorded_as_limitation():
    base_result = calculate_financial_scenario(
        make_assumptions(
            price="100",
            volume="300",
            variable_cost="95",
            fixed_costs="1000",
        )
    )

    result = calculate_sensitivity_analysis(base_result)
    price = item_by_input(
        result,
        FinancialInputName.SELLING_PRICE_PER_UNIT,
    )

    decrease_metrics = {
        impact.metric_name
        for impact in price.decrease.impacts
    }

    assert FinancialMetricName.OPERATING_RESULT in decrease_metrics
    assert FinancialMetricName.BREAK_EVEN_UNITS not in decrease_metrics
    assert any(
        "BREAK_EVEN_UNITS sensitivity impact" in limitation
        for limitation in result.limitations
    )


def test_rejects_non_base_finance_scenario():
    upside_result = calculate_financial_scenario(
        make_assumptions(
            scenario=FinancialScenarioKind.UPSIDE
        )
    )

    with pytest.raises(DecisionSensitivityError):
        calculate_sensitivity_analysis(upside_result)
