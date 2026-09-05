from decimal import (
    Decimal,
    ROUND_HALF_UP,
    localcontext,
)

from app.schemas.finance import (
    CalculatedFinancialMetric,
    FinancialAssumption,
    FinancialAssumptionSet,
    FinancialInputName,
    FinancialMetricName,
    FinancialPeriod,
    FinancialScenarioResult,
)
from app.services.finance_readiness import (
    evaluate_finance_readiness,
)


MONTHS_PER_YEAR = Decimal("12")

DIVISION_PRECISION = 28


class FinanceCalculationError(
    RuntimeError
):
    pass


def _divide(
    numerator: Decimal,
    denominator: Decimal,
) -> Decimal:
    if denominator == 0:
        raise FinanceCalculationError(
            "Cannot divide by zero"
        )

    with localcontext() as context:
        context.prec = DIVISION_PRECISION
        context.rounding = (
            ROUND_HALF_UP
        )

        return numerator / denominator


def _require_value(
    assumption: FinancialAssumption,
) -> Decimal:
    if assumption.value is None:
        raise FinanceCalculationError(
            "Finance calculator received "
            "a missing required input: "
            f"{assumption.input_name.value}"
        )

    return assumption.value


def _normalize_period_value(
    *,
    value: Decimal,
    source_period: FinancialPeriod,
    target_period: FinancialPeriod,
) -> Decimal:
    if source_period == target_period:
        return value

    if (
        source_period
        == FinancialPeriod.MONTHLY
        and target_period
        == FinancialPeriod.ANNUAL
    ):
        return value * MONTHS_PER_YEAR

    if (
        source_period
        == FinancialPeriod.ANNUAL
        and target_period
        == FinancialPeriod.MONTHLY
    ):
        return _divide(
            value,
            MONTHS_PER_YEAR,
        )

    raise FinanceCalculationError(
        "Unsupported financial period "
        "conversion"
    )


def _calculation_currency(
    assumptions: FinancialAssumptionSet,
) -> str:
    currency = (
        assumptions
        .selling_price_per_unit
        .currency
    )

    if currency is None:
        raise FinanceCalculationError(
            "Finance calculator requires "
            "a resolved core currency"
        )

    return currency


def _calculation_period(
    assumptions: FinancialAssumptionSet,
) -> FinancialPeriod:
    period = assumptions.sales_volume.period

    if period is None:
        raise FinanceCalculationError(
            "Sales volume must declare "
            "the calculation period"
        )

    return period


def _unit_label(
    assumptions: FinancialAssumptionSet,
) -> str:
    unit = (
        assumptions
        .sales_volume
        .unit_label
    )

    if unit is None:
        raise FinanceCalculationError(
            "Sales volume must declare "
            "a unit label"
        )

    return unit


def _money_metric(
    *,
    metric_name: FinancialMetricName,
    value: Decimal,
    currency: str,
    period: FinancialPeriod,
    formula: str,
    input_names: list[
        FinancialInputName
    ],
) -> CalculatedFinancialMetric:
    return CalculatedFinancialMetric(
        metric_name=metric_name,
        value=value,
        currency=currency,
        period=period,
        unit="money",
        formula=formula,
        input_names=input_names,
    )


def calculate_financial_scenario(
    assumptions: FinancialAssumptionSet,
) -> FinancialScenarioResult:
    readiness = (
        evaluate_finance_readiness(
            assumptions
        )
    )

    if not readiness.can_calculate_core:
        raise FinanceCalculationError(
            "Financial assumptions are not "
            "ready for calculation: "
            f"{readiness.status.value}"
        )

    price = _require_value(
        assumptions
        .selling_price_per_unit
    )

    volume = _require_value(
        assumptions.sales_volume
    )

    variable_cost_per_unit = (
        _require_value(
            assumptions
            .variable_cost_per_unit
        )
    )

    fixed_costs = _require_value(
        assumptions.fixed_costs
    )

    calculation_period = (
        _calculation_period(
            assumptions
        )
    )

    fixed_cost_period = (
        assumptions.fixed_costs.period
    )

    if fixed_cost_period is None:
        raise FinanceCalculationError(
            "Fixed costs must declare "
            "a financial period"
        )

    normalized_fixed_costs = (
        _normalize_period_value(
            value=fixed_costs,
            source_period=(
                fixed_cost_period
            ),
            target_period=(
                calculation_period
            ),
        )
    )

    currency = _calculation_currency(
        assumptions
    )

    unit_label = _unit_label(
        assumptions
    )

    revenue = (
        price
        * volume
    )

    variable_costs = (
        variable_cost_per_unit
        * volume
    )

    contribution_per_unit = (
        price
        - variable_cost_per_unit
    )

    contribution_profit = (
        revenue
        - variable_costs
    )

    operating_result = (
        contribution_profit
        - normalized_fixed_costs
    )

    metrics: list[
        CalculatedFinancialMetric
    ] = []

    limitations: list[str] = []

    metrics.append(
        _money_metric(
            metric_name=(
                FinancialMetricName
                .REVENUE
            ),
            value=revenue,
            currency=currency,
            period=calculation_period,
            formula=(
                "selling_price_per_unit "
                "* sales_volume"
            ),
            input_names=[
                FinancialInputName
                .SELLING_PRICE_PER_UNIT,
                FinancialInputName
                .SALES_VOLUME,
            ],
        )
    )

    metrics.append(
        _money_metric(
            metric_name=(
                FinancialMetricName
                .VARIABLE_COSTS
            ),
            value=variable_costs,
            currency=currency,
            period=calculation_period,
            formula=(
                "variable_cost_per_unit "
                "* sales_volume"
            ),
            input_names=[
                FinancialInputName
                .VARIABLE_COST_PER_UNIT,
                FinancialInputName
                .SALES_VOLUME,
            ],
        )
    )

    metrics.append(
        _money_metric(
            metric_name=(
                FinancialMetricName
                .CONTRIBUTION_PROFIT
            ),
            value=contribution_profit,
            currency=currency,
            period=calculation_period,
            formula=(
                "revenue "
                "- variable_costs"
            ),
            input_names=[
                FinancialInputName
                .SELLING_PRICE_PER_UNIT,
                FinancialInputName
                .VARIABLE_COST_PER_UNIT,
                FinancialInputName
                .SALES_VOLUME,
            ],
        )
    )

    if revenue > 0:
        contribution_margin = (
            _divide(
                contribution_profit,
                revenue,
            )
            * Decimal("100")
        )

        metrics.append(
            CalculatedFinancialMetric(
                metric_name=(
                    FinancialMetricName
                    .CONTRIBUTION_MARGIN_PERCENT
                ),
                value=(
                    contribution_margin
                ),
                currency=None,
                period=None,
                unit="percent",
                formula=(
                    "contribution_profit "
                    "/ revenue * 100"
                ),
                input_names=[
                    FinancialInputName
                    .SELLING_PRICE_PER_UNIT,
                    FinancialInputName
                    .VARIABLE_COST_PER_UNIT,
                    FinancialInputName
                    .SALES_VOLUME,
                ],
            )
        )

    else:
        limitations.append(
            "Contribution margin was not "
            "calculated because revenue "
            "is zero."
        )

    metrics.append(
        _money_metric(
            metric_name=(
                FinancialMetricName
                .OPERATING_RESULT
            ),
            value=operating_result,
            currency=currency,
            period=calculation_period,
            formula=(
                "contribution_profit "
                "- normalized_fixed_costs"
            ),
            input_names=[
                FinancialInputName
                .SELLING_PRICE_PER_UNIT,
                FinancialInputName
                .VARIABLE_COST_PER_UNIT,
                FinancialInputName
                .SALES_VOLUME,
                FinancialInputName
                .FIXED_COSTS,
            ],
        )
    )

    if contribution_per_unit > 0:
        break_even_units = _divide(
            normalized_fixed_costs,
            contribution_per_unit,
        )

        metrics.append(
            CalculatedFinancialMetric(
                metric_name=(
                    FinancialMetricName
                    .BREAK_EVEN_UNITS
                ),
                value=break_even_units,
                currency=None,
                period=calculation_period,
                unit=unit_label,
                formula=(
                    "normalized_fixed_costs "
                    "/ "
                    "(selling_price_per_unit "
                    "- variable_cost_per_unit)"
                ),
                input_names=[
                    FinancialInputName
                    .FIXED_COSTS,
                    FinancialInputName
                    .SELLING_PRICE_PER_UNIT,
                    FinancialInputName
                    .VARIABLE_COST_PER_UNIT,
                ],
            )
        )

    else:
        limitations.append(
            "Break-even units were not "
            "calculated because contribution "
            "per unit is not positive."
        )

    starting_cash = (
        assumptions.starting_cash
    )

    if (
        readiness.runway_input_ready
        and starting_cash is not None
        and starting_cash.value is not None
    ):
        if operating_result < 0:
            runway_periods = _divide(
                starting_cash.value,
                abs(operating_result),
            )

            runway_unit = (
                "months"
                if calculation_period
                == FinancialPeriod.MONTHLY
                else "years"
            )

            metrics.append(
                CalculatedFinancialMetric(
                    metric_name=(
                        FinancialMetricName
                        .RUNWAY_PERIODS
                    ),
                    value=runway_periods,
                    currency=None,
                    period=None,
                    unit=runway_unit,
                    formula=(
                        "starting_cash "
                        "/ abs(operating_result)"
                    ),
                    input_names=[
                        FinancialInputName
                        .STARTING_CASH,
                        FinancialInputName
                        .SELLING_PRICE_PER_UNIT,
                        FinancialInputName
                        .VARIABLE_COST_PER_UNIT,
                        FinancialInputName
                        .SALES_VOLUME,
                        FinancialInputName
                        .FIXED_COSTS,
                    ],
                )
            )

        else:
            limitations.append(
                "Runway is not applicable "
                "because the operating result "
                "is non-negative."
            )

    else:
        limitations.append(
            "Runway was not calculated "
            "because compatible starting "
            "cash is unavailable."
        )

    return FinancialScenarioResult(
        scenario=assumptions.scenario,
        assumptions=assumptions,
        metrics=metrics,
        missing_critical_inputs=[],
        limitations=limitations,
    )