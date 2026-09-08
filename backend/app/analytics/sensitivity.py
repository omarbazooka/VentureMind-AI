from decimal import (
    Decimal,
    ROUND_HALF_UP,
    localcontext,
)

from app.finance.calculator import (
    calculate_financial_scenario,
)
from app.schemas.analytics import (
    InputSensitivityResult,
    SensitivityAnalysisResult,
    SensitivityMetricImpact,
    SensitivityPoint,
)
from app.schemas.finance import (
    CalculatedFinancialMetric,
    FinancialAssumption,
    FinancialAssumptionSet,
    FinancialInputName,
    FinancialMetricName,
    FinancialScenarioKind,
    FinancialScenarioResult,
)


DIVISION_PRECISION = 28

DEFAULT_SENSITIVITY_INPUTS = (
    FinancialInputName.SELLING_PRICE_PER_UNIT,
    FinancialInputName.SALES_VOLUME,
    FinancialInputName.VARIABLE_COST_PER_UNIT,
    FinancialInputName.FIXED_COSTS,
)

DEFAULT_IMPACT_METRICS = (
    FinancialMetricName.REVENUE,
    FinancialMetricName.OPERATING_RESULT,
    FinancialMetricName.BREAK_EVEN_UNITS,
    FinancialMetricName.CONTRIBUTION_MARGIN_PERCENT,
)

INPUT_FIELD_BY_NAME = {
    FinancialInputName.SELLING_PRICE_PER_UNIT: (
        "selling_price_per_unit"
    ),
    FinancialInputName.SALES_VOLUME: "sales_volume",
    FinancialInputName.VARIABLE_COST_PER_UNIT: (
        "variable_cost_per_unit"
    ),
    FinancialInputName.FIXED_COSTS: "fixed_costs",
}


class DecisionSensitivityError(RuntimeError):
    pass


def _relative_change_percent(
    *,
    stressed_value: Decimal,
    base_value: Decimal,
) -> Decimal | None:
    if base_value == 0:
        return None

    with localcontext() as context:
        context.prec = DIVISION_PRECISION
        context.rounding = ROUND_HALF_UP
        return (
            (stressed_value - base_value)
            / abs(base_value)
            * Decimal("100")
        )


def _stress_assumptions(
    *,
    assumptions: FinancialAssumptionSet,
    input_name: FinancialInputName,
    input_change_percent: Decimal,
) -> FinancialAssumptionSet:
    field_name = INPUT_FIELD_BY_NAME.get(input_name)
    if field_name is None:
        raise DecisionSensitivityError(
            f"Unsupported sensitivity input: {input_name.value}"
        )

    assumption: FinancialAssumption = getattr(
        assumptions,
        field_name,
    )

    if assumption.value is None:
        raise DecisionSensitivityError(
            f"Sensitivity input is unresolved: {input_name.value}"
        )

    multiplier = (
        Decimal("1")
        + input_change_percent / Decimal("100")
    )
    stressed_value = assumption.value * multiplier

    stressed_assumption = assumption.model_copy(
        update={"value": stressed_value}
    )

    return assumptions.model_copy(
        update={field_name: stressed_assumption}
    )


def _metrics_by_name(
    result: FinancialScenarioResult,
) -> dict[FinancialMetricName, CalculatedFinancialMetric]:
    return {
        metric.metric_name: metric
        for metric in result.metrics
    }


def _validate_metric_basis(
    *,
    base_metric: CalculatedFinancialMetric,
    stressed_metric: CalculatedFinancialMetric,
) -> None:
    if (
        base_metric.currency != stressed_metric.currency
        or base_metric.unit != stressed_metric.unit
        or base_metric.period != stressed_metric.period
    ):
        raise DecisionSensitivityError(
            f"Sensitivity changed the measurement basis for "
            f"{base_metric.metric_name.value}"
        )


def _build_point(
    *,
    base_result: FinancialScenarioResult,
    input_name: FinancialInputName,
    input_change_percent: Decimal,
    impact_metrics: tuple[FinancialMetricName, ...],
) -> tuple[SensitivityPoint, list[str]]:
    stressed_assumptions = _stress_assumptions(
        assumptions=base_result.assumptions,
        input_name=input_name,
        input_change_percent=input_change_percent,
    )
    stressed_result = calculate_financial_scenario(
        stressed_assumptions
    )

    base_metrics = _metrics_by_name(base_result)
    stressed_metrics = _metrics_by_name(stressed_result)

    impacts: list[SensitivityMetricImpact] = []
    limitations: list[str] = []

    for metric_name in impact_metrics:
        base_metric = base_metrics.get(metric_name)
        stressed_metric = stressed_metrics.get(metric_name)

        if base_metric is None or stressed_metric is None:
            limitations.append(
                f"{metric_name.value} sensitivity impact for "
                f"{input_name.value} at {input_change_percent}% was "
                "not calculated because the metric is unavailable in "
                "the BASE or stressed Finance result."
            )
            continue

        _validate_metric_basis(
            base_metric=base_metric,
            stressed_metric=stressed_metric,
        )

        impacts.append(
            SensitivityMetricImpact(
                metric_name=metric_name,
                base_value=base_metric.value,
                stressed_value=stressed_metric.value,
                absolute_change=(
                    stressed_metric.value - base_metric.value
                ),
                relative_change_percent=(
                    _relative_change_percent(
                        stressed_value=stressed_metric.value,
                        base_value=base_metric.value,
                    )
                ),
                currency=base_metric.currency,
                unit=base_metric.unit,
                period=base_metric.period,
            )
        )

    if not impacts:
        raise DecisionSensitivityError(
            f"No comparable sensitivity metrics remain for "
            f"{input_name.value}"
        )

    return (
        SensitivityPoint(
            input_name=input_name,
            input_change_percent=input_change_percent,
            impacts=impacts,
        ),
        limitations,
    )


def _impact_for_metric(
    *,
    point: SensitivityPoint,
    metric_name: FinancialMetricName,
) -> SensitivityMetricImpact:
    for impact in point.impacts:
        if impact.metric_name == metric_name:
            return impact

    raise DecisionSensitivityError(
        f"Sensitivity point is missing ranking metric "
        f"{metric_name.value}"
    )


def calculate_sensitivity_analysis(
    base_result: FinancialScenarioResult,
    *,
    shock_percent: Decimal = Decimal("10"),
    ranking_metric: FinancialMetricName = (
        FinancialMetricName.OPERATING_RESULT
    ),
    impact_metrics: tuple[FinancialMetricName, ...] = (
        DEFAULT_IMPACT_METRICS
    ),
) -> SensitivityAnalysisResult:
    if base_result.scenario != FinancialScenarioKind.BASE:
        raise DecisionSensitivityError(
            "Decision sensitivity analysis requires the BASE Finance scenario"
        )

    if shock_percent <= 0 or shock_percent > 100:
        raise DecisionSensitivityError(
            "Sensitivity shock_percent must be greater than 0 and at most 100"
        )

    if ranking_metric not in impact_metrics:
        raise DecisionSensitivityError(
            "Sensitivity impact_metrics must include the ranking metric"
        )

    limitations: list[str] = []
    input_results: list[InputSensitivityResult] = []

    for input_name in DEFAULT_SENSITIVITY_INPUTS:
        decrease, decrease_limitations = _build_point(
            base_result=base_result,
            input_name=input_name,
            input_change_percent=-shock_percent,
            impact_metrics=impact_metrics,
        )
        increase, increase_limitations = _build_point(
            base_result=base_result,
            input_name=input_name,
            input_change_percent=shock_percent,
            impact_metrics=impact_metrics,
        )

        limitations.extend(decrease_limitations)
        limitations.extend(increase_limitations)

        decrease_ranking_impact = _impact_for_metric(
            point=decrease,
            metric_name=ranking_metric,
        )
        increase_ranking_impact = _impact_for_metric(
            point=increase,
            metric_name=ranking_metric,
        )

        ranking_changes = [
            abs(value)
            for value in (
                decrease_ranking_impact.relative_change_percent,
                increase_ranking_impact.relative_change_percent,
            )
            if value is not None
        ]

        max_change = (
            max(ranking_changes)
            if ranking_changes
            else None
        )

        input_results.append(
            InputSensitivityResult(
                input_name=input_name,
                decrease=decrease,
                increase=increase,
                max_abs_ranking_metric_change_percent=max_change,
                rank=None,
            )
        )

    rankable = [
        item
        for item in input_results
        if item.max_abs_ranking_metric_change_percent is not None
    ]

    if rankable:
        ranked = sorted(
            rankable,
            key=lambda item: (
                item.max_abs_ranking_metric_change_percent
            ),
            reverse=True,
        )
        rank_by_input = {
            item.input_name: rank
            for rank, item in enumerate(ranked, start=1)
        }
        input_results = [
            item.model_copy(
                update={
                    "rank": rank_by_input.get(item.input_name)
                }
            )
            for item in input_results
        ]
        input_results.sort(
            key=lambda item: (
                item.rank
                if item.rank is not None
                else len(input_results) + 1
            )
        )
    else:
        limitations.append(
            f"Sensitivity inputs were not ranked because the BASE "
            f"{ranking_metric.value} value is zero, so relative change "
            "is undefined."
        )

    return SensitivityAnalysisResult(
        shock_percent=shock_percent,
        ranking_metric=ranking_metric,
        inputs=input_results,
        limitations=limitations,
    )
