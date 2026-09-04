from decimal import Decimal

from app.schemas.finance import (
    FinanceReadinessIssueCode,
    FinanceReadinessStatus,
    FinancialAssumption,
    FinancialAssumptionProvenance,
    FinancialAssumptionSet,
    FinancialInputName,
    FinancialPeriod,
    FinancialScenarioKind,
)
from app.services.finance_readiness import (
    evaluate_finance_readiness,
)


def make_assumptions(
    *,
    price_value: (
        Decimal | None
    ) = Decimal("250"),
    price_currency: str = "EGP",
    volume_unit: str = "customer",
    variable_cost_currency: str = "EGP",
    starting_cash: (
        FinancialAssumption | None
    ) = None,
) -> FinancialAssumptionSet:
    price_known = (
        price_value is not None
    )

    return FinancialAssumptionSet(
        scenario=(
            FinancialScenarioKind.BASE
        ),

        selling_price_per_unit=(
            FinancialAssumption(
                input_name=(
                    FinancialInputName
                    .SELLING_PRICE_PER_UNIT
                ),
                value=price_value,
                provenance=(
                    FinancialAssumptionProvenance
                    .USER
                    if price_known
                    else None
                ),
                currency=price_currency,
                unit_label="customer",
                rationale=(
                    "Expected selling price."
                ),
                profile_fields=(
                    ["selling_price"]
                    if price_known
                    else []
                ),
            )
        ),

        sales_volume=(
            FinancialAssumption(
                input_name=(
                    FinancialInputName
                    .SALES_VOLUME
                ),
                value=Decimal("100"),
                provenance=(
                    FinancialAssumptionProvenance
                    .AI_ASSUMPTION
                ),
                unit_label=volume_unit,
                period=(
                    FinancialPeriod.MONTHLY
                ),
                rationale=(
                    "Temporary monthly "
                    "volume assumption."
                ),
            )
        ),

        variable_cost_per_unit=(
            FinancialAssumption(
                input_name=(
                    FinancialInputName
                    .VARIABLE_COST_PER_UNIT
                ),
                value=Decimal("50"),
                provenance=(
                    FinancialAssumptionProvenance
                    .AI_ASSUMPTION
                ),
                currency=(
                    variable_cost_currency
                ),
                unit_label="customer",
                rationale=(
                    "Temporary variable "
                    "cost assumption."
                ),
            )
        ),

        fixed_costs=(
            FinancialAssumption(
                input_name=(
                    FinancialInputName
                    .FIXED_COSTS
                ),
                value=Decimal("10000"),
                provenance=(
                    FinancialAssumptionProvenance
                    .USER
                ),
                currency="EGP",
                period=(
                    FinancialPeriod.MONTHLY
                ),
                rationale=(
                    "User supplied fixed "
                    "cost estimate."
                ),
                profile_fields=[
                    "monthly_fixed_costs"
                ],
            )
        ),

        starting_cash=starting_cash,
    )


def test_ready_core_without_starting_cash():
    result = (
        evaluate_finance_readiness(
            make_assumptions()
        )
    )

    assert (
        result.status
        == FinanceReadinessStatus
        .READY_FOR_CALCULATION
    )

    assert (
        result.can_calculate_core
        is True
    )

    assert (
        result.missing_critical_inputs
        == []
    )

    assert (
        result.blocking_issues
        == []
    )

    assert (
        FinanceReadinessIssueCode
        .STARTING_CASH_MISSING
        in result.optional_issues
    )

    assert (
        result.runway_input_ready
        is False
    )


def test_missing_price_blocks_calculation():
    result = (
        evaluate_finance_readiness(
            make_assumptions(
                price_value=None
            )
        )
    )

    assert (
        result.status
        == FinanceReadinessStatus
        .MISSING_CRITICAL_INPUTS
    )

    assert (
        result.can_calculate_core
        is False
    )

    assert (
        FinancialInputName
        .SELLING_PRICE_PER_UNIT
        in (
            result
            .missing_critical_inputs
        )
    )


def test_currency_mismatch_blocks_calculation():
    result = (
        evaluate_finance_readiness(
            make_assumptions(
                variable_cost_currency=(
                    "USD"
                )
            )
        )
    )

    assert (
        result.status
        == FinanceReadinessStatus
        .INCOMPATIBLE_INPUTS
    )

    assert (
        result.can_calculate_core
        is False
    )

    assert (
        FinanceReadinessIssueCode
        .CORE_CURRENCY_MISMATCH
        in result.blocking_issues
    )


def test_unit_mismatch_blocks_calculation():
    result = (
        evaluate_finance_readiness(
            make_assumptions(
                volume_unit=(
                    "subscription"
                )
            )
        )
    )

    assert (
        result.status
        == FinanceReadinessStatus
        .INCOMPATIBLE_INPUTS
    )

    assert (
        FinanceReadinessIssueCode
        .CORE_UNIT_MISMATCH
        in result.blocking_issues
    )


def test_matching_starting_cash_enables_runway_input():
    starting_cash = (
        FinancialAssumption(
            input_name=(
                FinancialInputName
                .STARTING_CASH
            ),
            value=Decimal("100000"),
            provenance=(
                FinancialAssumptionProvenance
                .USER
            ),
            currency="EGP",
            rationale=(
                "User supplied available cash."
            ),
            profile_fields=[
                "starting_cash"
            ],
        )
    )

    result = (
        evaluate_finance_readiness(
            make_assumptions(
                starting_cash=(
                    starting_cash
                )
            )
        )
    )

    assert (
        result.can_calculate_core
        is True
    )

    assert (
        result.runway_input_ready
        is True
    )

    assert (
        result.optional_issues
        == []
    )


def test_starting_cash_currency_mismatch_does_not_block_core():
    starting_cash = (
        FinancialAssumption(
            input_name=(
                FinancialInputName
                .STARTING_CASH
            ),
            value=Decimal("5000"),
            provenance=(
                FinancialAssumptionProvenance
                .USER
            ),
            currency="USD",
            rationale=(
                "User supplied cash."
            ),
            profile_fields=[
                "starting_cash"
            ],
        )
    )

    result = (
        evaluate_finance_readiness(
            make_assumptions(
                starting_cash=(
                    starting_cash
                )
            )
        )
    )

    assert (
        result.status
        == FinanceReadinessStatus
        .READY_FOR_CALCULATION
    )

    assert (
        result.can_calculate_core
        is True
    )

    assert (
        result.runway_input_ready
        is False
    )

    assert (
        FinanceReadinessIssueCode
        .STARTING_CASH_CURRENCY_MISMATCH
        in result.optional_issues
    )