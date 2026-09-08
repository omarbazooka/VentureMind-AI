from decimal import (
    Decimal,
    ROUND_HALF_UP,
    localcontext,
)

from app.schemas.analytics import (
    DecisionKPI,
    DecisionKPIName,
)
from app.schemas.finance import (
    FinancialInputName,
    FinancialMetricName,
    FinancialScenarioResult,
)


DIVISION_PRECISION = 28


def _percent(
    numerator: Decimal,
    denominator: Decimal,
) -> Decimal:
    with localcontext() as context:
        context.prec = DIVISION_PRECISION
        context.rounding = ROUND_HALF_UP
        return (
            numerator
            / denominator
            * Decimal("100")
        )


def calculate_decision_kpis(
    result: FinancialScenarioResult,
) -> tuple[list[DecisionKPI], list[str]]:
    metrics_by_name = {
        metric.metric_name: metric
        for metric in result.metrics
    }

    kpis: list[DecisionKPI] = []
    limitations: list[str] = []

    revenue = metrics_by_name.get(
        FinancialMetricName.REVENUE
    )
    operating_result = metrics_by_name.get(
        FinancialMetricName.OPERATING_RESULT
    )

    if revenue is None or operating_result is None:
        limitations.append(
            "Operating margin was not calculated because the Finance "
            "result is missing REVENUE or OPERATING_RESULT."
        )
    elif revenue.value == 0:
        limitations.append(
            "Operating margin was not calculated because revenue is zero."
        )
    else:
        kpis.append(
            DecisionKPI(
                metric_name=(
                    DecisionKPIName
                    .OPERATING_MARGIN_PERCENT
                ),
                scenario=result.scenario,
                value=_percent(
                    operating_result.value,
                    revenue.value,
                ),
                formula=(
                    "operating_result / revenue * 100"
                ),
                source_financial_metrics=[
                    FinancialMetricName.REVENUE,
                    FinancialMetricName.OPERATING_RESULT,
                ],
            )
        )

    break_even_units = metrics_by_name.get(
        FinancialMetricName.BREAK_EVEN_UNITS
    )
    sales_volume = result.assumptions.sales_volume.value

    if break_even_units is None:
        limitations.append(
            "Break-even headroom was not calculated because Finance "
            "did not produce BREAK_EVEN_UNITS."
        )
    elif sales_volume is None:
        limitations.append(
            "Break-even headroom was not calculated because sales volume "
            "is unresolved."
        )
    elif sales_volume == 0:
        limitations.append(
            "Break-even headroom was not calculated because sales volume "
            "is zero."
        )
    else:
        kpis.append(
            DecisionKPI(
                metric_name=(
                    DecisionKPIName
                    .BREAK_EVEN_HEADROOM_PERCENT
                ),
                scenario=result.scenario,
                value=_percent(
                    sales_volume - break_even_units.value,
                    sales_volume,
                ),
                formula=(
                    "(sales_volume - break_even_units) / sales_volume * 100"
                ),
                source_financial_metrics=[
                    FinancialMetricName.BREAK_EVEN_UNITS,
                ],
                source_financial_inputs=[
                    FinancialInputName.SALES_VOLUME,
                ],
            )
        )

    return kpis, limitations
