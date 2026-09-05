from decimal import Decimal

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


def make_annual_assumptions() -> FinancialAssumptionSet:
    return FinancialAssumptionSet(
        scenario=FinancialScenarioKind.BASE,
        selling_price_per_unit=FinancialAssumption(
            input_name=(
                FinancialInputName.SELLING_PRICE_PER_UNIT
            ),
            value=Decimal("250"),
            provenance=FinancialAssumptionProvenance.USER,
            currency="EGP",
            unit_label="customer",
            rationale="Selling price.",
            profile_fields=["selling_price"],
        ),
        sales_volume=FinancialAssumption(
            input_name=FinancialInputName.SALES_VOLUME,
            value=Decimal("1200"),
            provenance=(
                FinancialAssumptionProvenance.AI_ASSUMPTION
            ),
            unit_label="customer",
            period=FinancialPeriod.ANNUAL,
            rationale="Annual sales volume assumption.",
        ),
        variable_cost_per_unit=FinancialAssumption(
            input_name=(
                FinancialInputName.VARIABLE_COST_PER_UNIT
            ),
            value=Decimal("50"),
            provenance=(
                FinancialAssumptionProvenance.AI_ASSUMPTION
            ),
            currency="EGP",
            unit_label="customer",
            rationale="Variable cost per customer.",
        ),
        fixed_costs=FinancialAssumption(
            input_name=FinancialInputName.FIXED_COSTS,
            value=Decimal("10000"),
            provenance=FinancialAssumptionProvenance.USER,
            currency="EGP",
            period=FinancialPeriod.MONTHLY,
            rationale="Monthly fixed costs.",
            profile_fields=["fixed_costs"],
        ),
    )


def metric_by_name(result, metric_name):
    return next(
        metric
        for metric in result.metrics
        if metric.metric_name == metric_name
    )


def test_normalizes_monthly_fixed_costs_to_annual():
    result = calculate_financial_scenario(
        make_annual_assumptions()
    )

    operating_result = metric_by_name(
        result,
        FinancialMetricName.OPERATING_RESULT,
    )

    assert operating_result.value == Decimal("120000")
    assert operating_result.period == FinancialPeriod.ANNUAL

    break_even = metric_by_name(
        result,
        FinancialMetricName.BREAK_EVEN_UNITS,
    )

    assert break_even.value == Decimal("600")
    assert break_even.period == FinancialPeriod.ANNUAL
