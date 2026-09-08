from decimal import Decimal
from uuid import uuid4

from app.analytics.builder import (
    build_decision_analytics_result,
)
from app.finance.scenarios import (
    calculate_financial_scenarios,
)
from app.schemas.analytics import DecisionKPIName
from app.schemas.finance import (
    FinancialAssumption,
    FinancialAssumptionProvenance,
    FinancialAssumptionSet,
    FinancialInputName,
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
    fixed_costs: str,
) -> FinancialAssumptionSet:
    return FinancialAssumptionSet(
        scenario=scenario,
        selling_price_per_unit=FinancialAssumption(
            input_name=(
                FinancialInputName.SELLING_PRICE_PER_UNIT
            ),
            value=Decimal(price),
            provenance=(
                FinancialAssumptionProvenance.AI_ASSUMPTION
            ),
            currency="EGP",
            unit_label="customer",
            rationale="Scenario selling price.",
        ),
        sales_volume=FinancialAssumption(
            input_name=FinancialInputName.SALES_VOLUME,
            value=Decimal(volume),
            provenance=(
                FinancialAssumptionProvenance.AI_ASSUMPTION
            ),
            unit_label="customer",
            period=FinancialPeriod.MONTHLY,
            rationale="Scenario monthly volume.",
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
            rationale="Scenario variable cost.",
        ),
        fixed_costs=FinancialAssumption(
            input_name=FinancialInputName.FIXED_COSTS,
            value=Decimal(fixed_costs),
            provenance=(
                FinancialAssumptionProvenance.AI_ASSUMPTION
            ),
            currency="EGP",
            period=FinancialPeriod.MONTHLY,
            rationale="Scenario fixed costs.",
        ),
    )


def make_bundle(*, downside_price: str = "225"):
    return calculate_financial_scenarios(
        FinancialScenarioInputs(
            base=make_assumptions(
                scenario=FinancialScenarioKind.BASE,
                price="250",
                volume="100",
                variable_cost="50",
                fixed_costs="10000",
            ),
            upside=make_assumptions(
                scenario=FinancialScenarioKind.UPSIDE,
                price="275",
                volume="110",
                variable_cost="45",
                fixed_costs="9000",
            ),
            downside=make_assumptions(
                scenario=FinancialScenarioKind.DOWNSIDE,
                price=downside_price,
                volume="90",
                variable_cost="55",
                fixed_costs="11000",
            ),
        )
    )


def test_builds_grounded_decision_analytics_from_finance_bundle():
    finance_stage_run_id = uuid4()

    result = build_decision_analytics_result(
        finance_stage_run_id=finance_stage_run_id,
        finance_bundle=make_bundle(),
    )

    assert result.finance_stage_run_id == finance_stage_run_id
    assert len(result.kpis) == 6
    assert len(result.scenario_relative_changes) > 0
    assert result.sensitivity is not None
    assert result.sensitivity.inputs[0].rank == 1
    assert all(kpi.provenance == "CALCULATED" for kpi in result.kpis)

    operating_margin_scenarios = {
        kpi.scenario
        for kpi in result.kpis
        if (
            kpi.metric_name
            == DecisionKPIName.OPERATING_MARGIN_PERCENT
        )
    }
    assert operating_margin_scenarios == {
        FinancialScenarioKind.BASE,
        FinancialScenarioKind.UPSIDE,
        FinancialScenarioKind.DOWNSIDE,
    }


def test_preserves_analytics_limitations_when_downside_break_even_disappears():
    result = build_decision_analytics_result(
        finance_stage_run_id=uuid4(),
        finance_bundle=make_bundle(downside_price="40"),
    )

    assert any(
        "DOWNSIDE: Break-even headroom" in limitation
        for limitation in result.limitations
    )
    assert any(
        "BREAK_EVEN_UNITS" in limitation
        for limitation in result.limitations
    )
