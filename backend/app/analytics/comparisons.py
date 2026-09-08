from decimal import (
    Decimal,
    ROUND_HALF_UP,
    localcontext,
)

from app.schemas.analytics import ScenarioRelativeChange
from app.schemas.finance import (
    FinancialScenarioMetricComparison,
)


DIVISION_PRECISION = 28


class DecisionAnalyticsComparisonError(RuntimeError):
    pass


def _relative_change_percent(
    *,
    scenario_value: Decimal,
    base_value: Decimal,
) -> Decimal:
    with localcontext() as context:
        context.prec = DIVISION_PRECISION
        context.rounding = ROUND_HALF_UP
        return (
            (scenario_value - base_value)
            / abs(base_value)
            * Decimal("100")
        )


def calculate_scenario_relative_changes(
    comparisons: list[FinancialScenarioMetricComparison],
) -> tuple[list[ScenarioRelativeChange], list[str]]:
    metric_names = [
        comparison.metric_name
        for comparison in comparisons
    ]

    if len(metric_names) != len(set(metric_names)):
        raise DecisionAnalyticsComparisonError(
            "Finance comparisons contain duplicate metric names"
        )

    relative_changes: list[ScenarioRelativeChange] = []
    limitations: list[str] = []

    for comparison in comparisons:
        base_value = comparison.base_value
        upside_value = comparison.upside_value
        downside_value = comparison.downside_value

        upside_relative: Decimal | None = None
        downside_relative: Decimal | None = None

        if base_value is None:
            limitations.append(
                f"{comparison.metric_name.value} relative scenario changes "
                "were not calculated because the BASE value is unavailable."
            )
        elif base_value == 0:
            limitations.append(
                f"{comparison.metric_name.value} relative scenario changes "
                "were not calculated because the BASE value is zero."
            )
        else:
            if upside_value is None:
                limitations.append(
                    f"{comparison.metric_name.value} UPSIDE relative change "
                    "was not calculated because the UPSIDE value is unavailable."
                )
            else:
                upside_relative = _relative_change_percent(
                    scenario_value=upside_value,
                    base_value=base_value,
                )

            if downside_value is None:
                limitations.append(
                    f"{comparison.metric_name.value} DOWNSIDE relative change "
                    "was not calculated because the DOWNSIDE value is unavailable."
                )
            else:
                downside_relative = _relative_change_percent(
                    scenario_value=downside_value,
                    base_value=base_value,
                )

        relative_changes.append(
            ScenarioRelativeChange(
                metric_name=comparison.metric_name,
                upside_relative_change_percent=(
                    upside_relative
                ),
                downside_relative_change_percent=(
                    downside_relative
                ),
            )
        )

    return relative_changes, limitations
