from decimal import Decimal

from app.analytics.calculator import (
    calculate_decision_kpis,
)
from app.finance.calculator import (
    calculate_financial_scenario,
)
from app.schemas.analytics import DecisionKPIName
from app.schemas.finance import (
    FinancialAssumption,
    FinancialAssumptionProvenance,
    FinancialAssumptionSet,
    FinancialInputName,
    FinancialPeriod,
    FinancialScenarioKind,
)


def make_assumptions(
    *,
    price: str = "250",
    volume: str = "100",
    variable_cost: str = "50",
    fixed_costs: str = "10000",
) -> FinancialAssumptionSet:
    return FinancialAssumptionSet(
        scenario=FinancialScenarioKind.BASE,
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


def kpi_by_name(kpis, metric_name):
    return next(
        kpi
        for kpi in kpis
        if kpi.metric_name == metric_name
    )


def test_calculates_operating_margin_and_break_even_headroom():
    finance_result = calculate_financial_scenario(
        make_assumptions()
    )

    kpis, limitations = calculate_decision_kpis(
        finance_result
    )

    operating_margin = kpi_by_name(
        kpis,
        DecisionKPIName.OPERATING_MARGIN_PERCENT,
    )
    headroom = kpi_by_name(
        kpis,
        DecisionKPIName.BREAK_EVEN_HEADROOM_PERCENT,
    )

    assert operating_margin.value == Decimal("40.0")
    assert headroom.value == Decimal("50.0")
    assert operating_margin.provenance == "CALCULATED"
    assert headroom.provenance == "CALCULATED"
    assert limitations == []


def test_break_even_headroom_can_be_negative_below_break_even():
    finance_result = calculate_financial_scenario(
        make_assumptions(volume="25")
    )

    kpis, limitations = calculate_decision_kpis(
        finance_result
    )

    headroom = kpi_by_name(
        kpis,
        DecisionKPIName.BREAK_EVEN_HEADROOM_PERCENT,
    )

    assert headroom.value == Decimal("-100")
    assert limitations == []


def test_zero_revenue_omits_operating_margin_instead_of_dividing_by_zero():
    finance_result = calculate_financial_scenario(
        make_assumptions(
            price="0",
            variable_cost="0",
            fixed_costs="0",
        )
    )

    kpis, limitations = calculate_decision_kpis(
        finance_result
    )

    names = {kpi.metric_name for kpi in kpis}

    assert (
        DecisionKPIName.OPERATING_MARGIN_PERCENT
        not in names
    )
    assert any(
        "revenue is zero" in limitation
        for limitation in limitations
    )


def test_zero_sales_volume_omits_break_even_headroom():
    finance_result = calculate_financial_scenario(
        make_assumptions(volume="0")
    )

    kpis, limitations = calculate_decision_kpis(
        finance_result
    )

    names = {kpi.metric_name for kpi in kpis}

    assert (
        DecisionKPIName.BREAK_EVEN_HEADROOM_PERCENT
        not in names
    )
    assert any(
        "sales volume is zero" in limitation
        for limitation in limitations
    )
