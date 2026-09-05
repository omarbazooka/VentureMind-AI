from decimal import Decimal

from app.finance.calculator import (
    calculate_financial_scenario,
)
from app.schemas.finance import (
    CalculatedFinancialMetric,
    FinancialAssumptionSet,
    FinancialMetricName,
    FinancialPeriod,
    FinancialScenarioBundle,
    FinancialScenarioInputs,
    FinancialScenarioMetricComparison,
)


class FinanceScenarioError(
    RuntimeError
):
    pass


def _normalized_unit(
    assumptions: FinancialAssumptionSet,
) -> str:
    unit = (
        assumptions
        .sales_volume
        .unit_label
    )

    if unit is None:
        raise FinanceScenarioError(
            "Scenario sales volume must "
            "declare a unit label"
        )

    return unit.strip().casefold()


def _core_currency(
    assumptions: FinancialAssumptionSet,
) -> str:
    currency = (
        assumptions
        .selling_price_per_unit
        .currency
    )

    if currency is None:
        raise FinanceScenarioError(
            "Scenario must declare a "
            "core currency"
        )

    return currency


def _calculation_period(
    assumptions: FinancialAssumptionSet,
) -> FinancialPeriod:
    period = (
        assumptions
        .sales_volume
        .period
    )

    if period is None:
        raise FinanceScenarioError(
            "Scenario sales volume must "
            "declare a calculation period"
        )

    return period


def _validate_comparable_basis(
    inputs: FinancialScenarioInputs,
) -> None:
    scenarios = (
        inputs.base,
        inputs.upside,
        inputs.downside,
    )

    currencies = {
        _core_currency(assumptions)
        for assumptions in scenarios
    }

    if len(currencies) != 1:
        raise FinanceScenarioError(
            "Financial scenarios must use "
            "the same core currency"
        )

    units = {
        _normalized_unit(assumptions)
        for assumptions in scenarios
    }

    if len(units) != 1:
        raise FinanceScenarioError(
            "Financial scenarios must use "
            "the same sales-volume unit"
        )

    periods = {
        _calculation_period(assumptions)
        for assumptions in scenarios
    }

    if len(periods) != 1:
        raise FinanceScenarioError(
            "Financial scenarios must use "
            "the same calculation period"
        )


def _metrics_by_name(
    metrics: list[
        CalculatedFinancialMetric
    ],
) -> dict[
    FinancialMetricName,
    CalculatedFinancialMetric,
]:
    return {
        metric.metric_name: metric
        for metric in metrics
    }


def _first_available_metric(
    *,
    base: CalculatedFinancialMetric | None,
    upside: CalculatedFinancialMetric | None,
    downside: (
        CalculatedFinancialMetric | None
    ),
) -> CalculatedFinancialMetric:
    for metric in (
        base,
        upside,
        downside,
    ):
        if metric is not None:
            return metric

    raise FinanceScenarioError(
        "Metric comparison requires at "
        "least one available metric"
    )


def _validate_metric_metadata(
    *,
    metric_name: FinancialMetricName,
    metrics: tuple[
        CalculatedFinancialMetric | None,
        CalculatedFinancialMetric | None,
        CalculatedFinancialMetric | None,
    ],
) -> None:
    available = [
        metric
        for metric in metrics
        if metric is not None
    ]

    if len(available) <= 1:
        return

    currencies = {
        metric.currency
        for metric in available
    }

    units = {
        metric.unit
        for metric in available
    }

    periods = {
        metric.period
        for metric in available
    }

    if len(currencies) != 1:
        raise FinanceScenarioError(
            f"{metric_name.value} has "
            "incompatible currencies "
            "across scenarios"
        )

    if len(units) != 1:
        raise FinanceScenarioError(
            f"{metric_name.value} has "
            "incompatible units "
            "across scenarios"
        )

    if len(periods) != 1:
        raise FinanceScenarioError(
            f"{metric_name.value} has "
            "incompatible periods "
            "across scenarios"
        )


def _delta(
    *,
    scenario_value: Decimal | None,
    base_value: Decimal | None,
) -> Decimal | None:
    if (
        scenario_value is None
        or base_value is None
    ):
        return None

    return (
        scenario_value
        - base_value
    )


def calculate_financial_scenarios(
    inputs: FinancialScenarioInputs,
) -> FinancialScenarioBundle:
    _validate_comparable_basis(
        inputs
    )

    base = calculate_financial_scenario(
        inputs.base
    )

    upside = calculate_financial_scenario(
        inputs.upside
    )

    downside = calculate_financial_scenario(
        inputs.downside
    )

    base_metrics = _metrics_by_name(
        base.metrics
    )

    upside_metrics = _metrics_by_name(
        upside.metrics
    )

    downside_metrics = _metrics_by_name(
        downside.metrics
    )

    metric_names = (
        set(base_metrics)
        | set(upside_metrics)
        | set(downside_metrics)
    )

    comparisons: list[
        FinancialScenarioMetricComparison
    ] = []

    limitations: list[str] = []

    for metric_name in sorted(
        metric_names,
        key=lambda item: item.value,
    ):
        base_metric = base_metrics.get(
            metric_name
        )

        upside_metric = (
            upside_metrics.get(
                metric_name
            )
        )

        downside_metric = (
            downside_metrics.get(
                metric_name
            )
        )

        metric_tuple = (
            base_metric,
            upside_metric,
            downside_metric,
        )

        _validate_metric_metadata(
            metric_name=metric_name,
            metrics=metric_tuple,
        )

        metadata_source = (
            _first_available_metric(
                base=base_metric,
                upside=upside_metric,
                downside=downside_metric,
            )
        )

        base_value = (
            base_metric.value
            if base_metric is not None
            else None
        )

        upside_value = (
            upside_metric.value
            if upside_metric is not None
            else None
        )

        downside_value = (
            downside_metric.value
            if downside_metric is not None
            else None
        )

        comparisons.append(
            FinancialScenarioMetricComparison(
                metric_name=metric_name,
                base_value=base_value,
                upside_value=upside_value,
                downside_value=(
                    downside_value
                ),
                upside_delta_from_base=(
                    _delta(
                        scenario_value=(
                            upside_value
                        ),
                        base_value=(
                            base_value
                        ),
                    )
                ),
                downside_delta_from_base=(
                    _delta(
                        scenario_value=(
                            downside_value
                        ),
                        base_value=(
                            base_value
                        ),
                    )
                ),
                currency=(
                    metadata_source.currency
                ),
                unit=metadata_source.unit,
                period=(
                    metadata_source.period
                ),
            )
        )

        if (
            base_metric is None
            or upside_metric is None
            or downside_metric is None
        ):
            limitations.append(
                f"{metric_name.value} is "
                "not available in every "
                "financial scenario."
            )

    return FinancialScenarioBundle(
        base=base,
        upside=upside,
        downside=downside,
        comparisons=comparisons,
        limitations=limitations,
    )