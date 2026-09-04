from app.schemas.finance import (
    FinanceReadinessIssueCode,
    FinanceReadinessResult,
    FinanceReadinessStatus,
    FinancialAssumption,
    FinancialAssumptionSet,
    FinancialInputName,
)


CRITICAL_FINANCE_INPUTS = (
    FinancialInputName
    .SELLING_PRICE_PER_UNIT,

    FinancialInputName
    .SALES_VOLUME,

    FinancialInputName
    .VARIABLE_COST_PER_UNIT,

    FinancialInputName
    .FIXED_COSTS,
)


def _critical_assumptions(
    assumptions: FinancialAssumptionSet,
) -> tuple[
    FinancialAssumption,
    ...,
]:
    return (
        assumptions
        .selling_price_per_unit,

        assumptions.sales_volume,

        assumptions
        .variable_cost_per_unit,

        assumptions.fixed_costs,
    )


def _missing_critical_inputs(
    assumptions: FinancialAssumptionSet,
) -> list[
    FinancialInputName
]:
    missing: list[
        FinancialInputName
    ] = []

    for assumption in (
        _critical_assumptions(
            assumptions
        )
    ):
        if assumption.value is None:
            missing.append(
                assumption.input_name
            )

    return missing


def _has_core_currency_mismatch(
    assumptions: FinancialAssumptionSet,
) -> bool:
    monetary_assumptions = (
        assumptions
        .selling_price_per_unit,

        assumptions
        .variable_cost_per_unit,

        assumptions.fixed_costs,
    )

    known_currencies = {
        assumption.currency
        for assumption
        in monetary_assumptions
        if assumption.value is not None
    }

    return len(
        known_currencies
    ) > 1


def _normalize_unit_label(
    assumption: FinancialAssumption,
) -> str | None:
    if assumption.unit_label is None:
        return None

    return (
        assumption.unit_label
        .strip()
        .casefold()
    )


def _has_core_unit_mismatch(
    assumptions: FinancialAssumptionSet,
) -> bool:
    unit_assumptions = (
        assumptions
        .selling_price_per_unit,

        assumptions.sales_volume,

        assumptions
        .variable_cost_per_unit,
    )

    known_units = {
        _normalize_unit_label(
            assumption
        )
        for assumption
        in unit_assumptions
        if assumption.value is not None
    }

    known_units.discard(None)

    return len(
        known_units
    ) > 1


def _resolved_core_currency(
    assumptions: FinancialAssumptionSet,
) -> str | None:
    monetary_assumptions = (
        assumptions
        .selling_price_per_unit,

        assumptions
        .variable_cost_per_unit,

        assumptions.fixed_costs,
    )

    currencies = {
        assumption.currency
        for assumption
        in monetary_assumptions
        if assumption.value is not None
    }

    if len(currencies) != 1:
        return None

    return next(
        iter(currencies)
    )


def evaluate_finance_readiness(
    assumptions: FinancialAssumptionSet,
) -> FinanceReadinessResult:
    missing_inputs = (
        _missing_critical_inputs(
            assumptions
        )
    )

    blocking_issues: list[
        FinanceReadinessIssueCode
    ] = []

    if _has_core_currency_mismatch(
        assumptions
    ):
        blocking_issues.append(
            FinanceReadinessIssueCode
            .CORE_CURRENCY_MISMATCH
        )

    if _has_core_unit_mismatch(
        assumptions
    ):
        blocking_issues.append(
            FinanceReadinessIssueCode
            .CORE_UNIT_MISMATCH
        )

    if missing_inputs:
        status = (
            FinanceReadinessStatus
            .MISSING_CRITICAL_INPUTS
        )

        can_calculate_core = False

    elif blocking_issues:
        status = (
            FinanceReadinessStatus
            .INCOMPATIBLE_INPUTS
        )

        can_calculate_core = False

    else:
        status = (
            FinanceReadinessStatus
            .READY_FOR_CALCULATION
        )

        can_calculate_core = True

    optional_issues: list[
        FinanceReadinessIssueCode
    ] = []

    runway_input_ready = False

    starting_cash = (
        assumptions.starting_cash
    )

    if (
        starting_cash is None
        or starting_cash.value is None
    ):
        optional_issues.append(
            FinanceReadinessIssueCode
            .STARTING_CASH_MISSING
        )

    elif can_calculate_core:
        core_currency = (
            _resolved_core_currency(
                assumptions
            )
        )

        if (
            starting_cash.currency
            != core_currency
        ):
            optional_issues.append(
                FinanceReadinessIssueCode
                .STARTING_CASH_CURRENCY_MISMATCH
            )

        else:
            runway_input_ready = True

    return FinanceReadinessResult(
        scenario=assumptions.scenario,
        status=status,
        can_calculate_core=(
            can_calculate_core
        ),
        missing_critical_inputs=(
            missing_inputs
        ),
        blocking_issues=(
            blocking_issues
        ),
        optional_issues=(
            optional_issues
        ),
        runway_input_ready=(
            runway_input_ready
        ),
    )