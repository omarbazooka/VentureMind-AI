from decimal import Decimal

import pytest

from app.analytics.comparisons import (
    DecisionAnalyticsComparisonError,
    calculate_scenario_relative_changes,
)
from app.schemas.finance import (
    FinancialMetricName,
    FinancialPeriod,
    FinancialScenarioMetricComparison,
)


def make_comparison(
    *,
    base: str | None = "100",
    upside: str | None = "150",
    downside: str | None = "50",
) -> FinancialScenarioMetricComparison:
    def value(raw: str | None) -> Decimal | None:
        return Decimal(raw) if raw is not None else None

    base_value = value(base)
    upside_value = value(upside)
    downside_value = value(downside)

    return FinancialScenarioMetricComparison(
        metric_name=FinancialMetricName.OPERATING_RESULT,
        base_value=base_value,
        upside_value=upside_value,
        downside_value=downside_value,
        upside_delta_from_base=(
            upside_value - base_value
            if upside_value is not None and base_value is not None
            else None
        ),
        downside_delta_from_base=(
            downside_value - base_value
            if downside_value is not None and base_value is not None
            else None
        ),
        currency="EGP",
        unit="money",
        period=FinancialPeriod.MONTHLY,
    )


def test_calculates_relative_changes_from_positive_base():
    results, limitations = calculate_scenario_relative_changes(
        [make_comparison()]
    )

    assert results[0].upside_relative_change_percent == Decimal("50")
    assert results[0].downside_relative_change_percent == Decimal("-50")
    assert limitations == []


def test_negative_base_uses_absolute_base_for_directional_change():
    results, limitations = calculate_scenario_relative_changes(
        [
            make_comparison(
                base="-100",
                upside="-50",
                downside="-150",
            )
        ]
    )

    assert results[0].upside_relative_change_percent == Decimal("50")
    assert results[0].downside_relative_change_percent == Decimal("-50")
    assert limitations == []


def test_zero_base_returns_no_relative_percentage():
    results, limitations = calculate_scenario_relative_changes(
        [
            make_comparison(
                base="0",
                upside="10",
                downside="-10",
            )
        ]
    )

    assert results[0].upside_relative_change_percent is None
    assert results[0].downside_relative_change_percent is None
    assert any(
        "BASE value is zero" in limitation
        for limitation in limitations
    )


def test_missing_scenario_value_returns_partial_comparison():
    results, limitations = calculate_scenario_relative_changes(
        [make_comparison(upside=None)]
    )

    assert results[0].upside_relative_change_percent is None
    assert results[0].downside_relative_change_percent == Decimal("-50")
    assert any(
        "UPSIDE value is unavailable" in limitation
        for limitation in limitations
    )


def test_duplicate_finance_comparison_metrics_are_rejected():
    comparison = make_comparison()

    with pytest.raises(DecisionAnalyticsComparisonError):
        calculate_scenario_relative_changes(
            [comparison, comparison]
        )
