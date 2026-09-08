from decimal import Decimal
from uuid import UUID

from app.analytics.calculator import calculate_decision_kpis
from app.analytics.comparisons import (
    calculate_scenario_relative_changes,
)
from app.analytics.sensitivity import (
    calculate_sensitivity_analysis,
)
from app.schemas.analytics import DecisionAnalyticsResult
from app.schemas.finance import (
    FinancialScenarioBundle,
)


MAX_ANALYTICS_LIMITATIONS = 30


def _bounded_unique_limitations(
    groups: list[list[str]],
) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()

    for group in groups:
        for limitation in group:
            if limitation in seen:
                continue
            seen.add(limitation)
            unique.append(limitation)

    if len(unique) <= MAX_ANALYTICS_LIMITATIONS:
        return unique

    return [
        *unique[: MAX_ANALYTICS_LIMITATIONS - 1],
        (
            "Additional Decision Analytics limitations were omitted "
            "after reaching the structured limit."
        ),
    ]


def build_decision_analytics_result(
    *,
    finance_stage_run_id: UUID,
    finance_bundle: FinancialScenarioBundle,
    sensitivity_shock_percent: Decimal = Decimal("10"),
) -> DecisionAnalyticsResult:
    kpis = []
    kpi_limitations: list[str] = []

    for scenario_result in (
        finance_bundle.base,
        finance_bundle.upside,
        finance_bundle.downside,
    ):
        scenario_kpis, scenario_limitations = (
            calculate_decision_kpis(
                scenario_result
            )
        )
        kpis.extend(scenario_kpis)
        kpi_limitations.extend(
            [
                f"{scenario_result.scenario.value}: {limitation}"
                for limitation in scenario_limitations
            ]
        )

    relative_changes, comparison_limitations = (
        calculate_scenario_relative_changes(
            finance_bundle.comparisons
        )
    )

    sensitivity = calculate_sensitivity_analysis(
        finance_bundle.base,
        shock_percent=sensitivity_shock_percent,
    )

    limitations = _bounded_unique_limitations(
        [
            [
                f"Finance comparison: {limitation}"
                for limitation in finance_bundle.limitations
            ],
            kpi_limitations,
            comparison_limitations,
            sensitivity.limitations,
        ]
    )

    return DecisionAnalyticsResult(
        finance_stage_run_id=finance_stage_run_id,
        kpis=kpis,
        scenario_relative_changes=relative_changes,
        sensitivity=sensitivity,
        limitations=limitations,
    )
