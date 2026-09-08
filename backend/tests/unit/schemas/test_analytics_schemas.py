from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.analytics import (
    DecisionAnalyticsResult,
    DecisionKPI,
    DecisionKPIName,
    InputSensitivityResult,
    ScenarioRelativeChange,
    SensitivityAnalysisResult,
    SensitivityMetricImpact,
    SensitivityPoint,
)
from app.schemas.finance import (
    FinancialInputName,
    FinancialMetricName,
    FinancialPeriod,
    FinancialScenarioKind,
)


def _operating_result_impact(
    *,
    stressed_value: str,
    relative_change_percent: str,
) -> SensitivityMetricImpact:
    stressed = Decimal(stressed_value)
    base = Decimal("100")
    return SensitivityMetricImpact(
        metric_name=FinancialMetricName.OPERATING_RESULT,
        base_value=base,
        stressed_value=stressed,
        absolute_change=stressed - base,
        relative_change_percent=Decimal(relative_change_percent),
        currency="usd",
        unit="currency",
        period=FinancialPeriod.MONTHLY,
    )


def _selling_price_sensitivity() -> InputSensitivityResult:
    return InputSensitivityResult(
        input_name=FinancialInputName.SELLING_PRICE_PER_UNIT,
        decrease=SensitivityPoint(
            input_name=FinancialInputName.SELLING_PRICE_PER_UNIT,
            input_change_percent=Decimal("-10"),
            impacts=[
                _operating_result_impact(
                    stressed_value="50",
                    relative_change_percent="-50",
                )
            ],
        ),
        increase=SensitivityPoint(
            input_name=FinancialInputName.SELLING_PRICE_PER_UNIT,
            input_change_percent=Decimal("10"),
            impacts=[
                _operating_result_impact(
                    stressed_value="150",
                    relative_change_percent="50",
                )
            ],
        ),
        max_abs_ranking_metric_change_percent=Decimal("50"),
        rank=1,
    )


def test_decision_analytics_result_accepts_grounded_calculated_contract() -> None:
    result = DecisionAnalyticsResult(
        finance_stage_run_id=uuid4(),
        kpis=[
            DecisionKPI(
                metric_name=DecisionKPIName.OPERATING_MARGIN_PERCENT,
                scenario=FinancialScenarioKind.BASE,
                value=Decimal("20"),
                formula="operating_result / revenue * 100",
                source_financial_metrics=[
                    FinancialMetricName.REVENUE,
                    FinancialMetricName.OPERATING_RESULT,
                ],
            )
        ],
        scenario_relative_changes=[
            ScenarioRelativeChange(
                metric_name=FinancialMetricName.OPERATING_RESULT,
                upside_relative_change_percent=Decimal("50"),
                downside_relative_change_percent=Decimal("-150"),
            )
        ],
        sensitivity=SensitivityAnalysisResult(
            shock_percent=Decimal("10"),
            ranking_metric=FinancialMetricName.OPERATING_RESULT,
            inputs=[_selling_price_sensitivity()],
        ),
    )

    assert result.kpis[0].provenance == "CALCULATED"
    assert (
        result.sensitivity.inputs[0].decrease.impacts[0].currency
        == "USD"
    )


def test_operating_margin_requires_revenue_and_operating_result_lineage() -> None:
    with pytest.raises(ValidationError):
        DecisionKPI(
            metric_name=DecisionKPIName.OPERATING_MARGIN_PERCENT,
            scenario=FinancialScenarioKind.BASE,
            value=Decimal("20"),
            formula="operating_result / revenue * 100",
            source_financial_metrics=[FinancialMetricName.REVENUE],
        )


def test_sensitivity_points_must_follow_declared_shock_percent() -> None:
    sensitivity = _selling_price_sensitivity()
    sensitivity.decrease.input_change_percent = Decimal("-5")

    with pytest.raises(ValidationError):
        SensitivityAnalysisResult(
            shock_percent=Decimal("10"),
            ranking_metric=FinancialMetricName.OPERATING_RESULT,
            inputs=[sensitivity],
        )


def test_sensitivity_relative_change_is_not_allowed_for_zero_base() -> None:
    with pytest.raises(ValidationError):
        SensitivityMetricImpact(
            metric_name=FinancialMetricName.OPERATING_RESULT,
            base_value=Decimal("0"),
            stressed_value=Decimal("10"),
            absolute_change=Decimal("10"),
            relative_change_percent=Decimal("100"),
            currency="USD",
            unit="currency",
            period=FinancialPeriod.MONTHLY,
        )


def test_decision_analytics_rejects_duplicate_kpi_scenario_pairs() -> None:
    kpi = DecisionKPI(
        metric_name=DecisionKPIName.OPERATING_MARGIN_PERCENT,
        scenario=FinancialScenarioKind.BASE,
        value=Decimal("20"),
        formula="operating_result / revenue * 100",
        source_financial_metrics=[
            FinancialMetricName.REVENUE,
            FinancialMetricName.OPERATING_RESULT,
        ],
    )

    with pytest.raises(ValidationError):
        DecisionAnalyticsResult(
            finance_stage_run_id=uuid4(),
            kpis=[kpi, kpi.model_copy()],
        )
