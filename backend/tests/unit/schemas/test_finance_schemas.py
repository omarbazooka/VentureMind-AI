from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.finance import (
    CalculatedFinancialMetric,
    FinancialAssumption,
    FinancialAssumptionProvenance,
    FinancialAssumptionSet,
    FinancialInputName,
    FinancialMetricName,
    FinancialPeriod,
    FinancialScenarioKind,
)


def make_user_price(
) -> FinancialAssumption:
    return FinancialAssumption(
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        value=Decimal("250"),
        provenance=(
            FinancialAssumptionProvenance
            .USER
        ),
        currency="egp",
        unit_label="customer",
        rationale=(
            "User supplied expected "
            "selling price."
        ),
        profile_fields=[
            "selling_price"
        ],
    )


def make_base_assumptions(
) -> FinancialAssumptionSet:
    return FinancialAssumptionSet(
        scenario=(
            FinancialScenarioKind.BASE
        ),
        selling_price_per_unit=(
            make_user_price()
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
                unit_label="customer",
                period=(
                    FinancialPeriod.MONTHLY
                ),
                rationale=(
                    "Temporary monthly "
                    "sales-volume assumption."
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
                currency="EGP",
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
                    "User supplied monthly "
                    "fixed-cost estimate."
                ),
                profile_fields=[
                    "monthly_fixed_costs"
                ],
            )
        ),
    )


def test_valid_financial_assumption_set():
    assumptions = (
        make_base_assumptions()
    )

    assert (
        assumptions
        .selling_price_per_unit
        .currency
        == "EGP"
    )

    assert (
        assumptions.scenario
        == FinancialScenarioKind.BASE
    )


def test_known_value_requires_provenance():
    with pytest.raises(
        ValidationError
    ):
        FinancialAssumption(
            input_name=(
                FinancialInputName
                .SELLING_PRICE_PER_UNIT
            ),
            value=Decimal("250"),
            currency="EGP",
            unit_label="customer",
            rationale="Price.",
        )


def test_user_value_requires_profile_lineage():
    with pytest.raises(
        ValidationError
    ):
        FinancialAssumption(
            input_name=(
                FinancialInputName
                .SELLING_PRICE_PER_UNIT
            ),
            value=Decimal("250"),
            provenance=(
                FinancialAssumptionProvenance
                .USER
            ),
            currency="EGP",
            unit_label="customer",
            rationale="User price.",
        )


def test_web_value_requires_evidence():
    with pytest.raises(
        ValidationError
    ):
        FinancialAssumption(
            input_name=(
                FinancialInputName
                .SELLING_PRICE_PER_UNIT
            ),
            value=Decimal("250"),
            provenance=(
                FinancialAssumptionProvenance
                .WEB
            ),
            currency="EGP",
            unit_label="customer",
            rationale=(
                "Research-supported price."
            ),
            supporting_stages=[
                AnalysisStage
                .COMPETITOR_INTELLIGENCE
            ],
        )


def test_ai_assumption_cannot_claim_evidence():
    with pytest.raises(
        ValidationError
    ):
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
            currency="EGP",
            unit_label="customer",
            rationale="Assumption.",
            evidence_source_ids=[
                "fake-source"
            ],
        )


def test_unknown_value_cannot_claim_lineage():
    with pytest.raises(
        ValidationError
    ):
        FinancialAssumption(
            input_name=(
                FinancialInputName
                .SELLING_PRICE_PER_UNIT
            ),
            value=None,
            currency="EGP",
            unit_label="customer",
            rationale=(
                "Selling price is unknown."
            ),
            profile_fields=[
                "selling_price"
            ],
        )


def test_assumption_slot_rejects_wrong_input():
    with pytest.raises(
        ValidationError
    ):
        FinancialAssumptionSet(
            scenario=(
                FinancialScenarioKind.BASE
            ),
            selling_price_per_unit=(
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
                    currency="EGP",
                    unit_label="customer",
                    rationale="Cost.",
                )
            ),
            sales_volume=(
                make_base_assumptions()
                .sales_volume
            ),
            variable_cost_per_unit=(
                make_base_assumptions()
                .variable_cost_per_unit
            ),
            fixed_costs=(
                make_base_assumptions()
                .fixed_costs
            ),
        )


def test_calculated_metric_is_explicitly_calculated():
    metric = CalculatedFinancialMetric(
        metric_name=(
            FinancialMetricName.REVENUE
        ),
        value=Decimal("25000"),
        currency="egp",
        period=FinancialPeriod.MONTHLY,
        unit="money_per_month",
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

    assert metric.currency == "EGP"
    assert (
        metric.provenance
        == "CALCULATED"
    )

def test_starting_cash_rejects_unit_label():
    with pytest.raises(
        ValidationError
    ):
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
            unit_label="customer",
            rationale="Available cash.",
            profile_fields=[
                "starting_cash"
            ],
        )


def test_price_rejects_period():
    with pytest.raises(
        ValidationError
    ):
        FinancialAssumption(
            input_name=(
                FinancialInputName
                .SELLING_PRICE_PER_UNIT
            ),
            value=Decimal("250"),
            provenance=(
                FinancialAssumptionProvenance
                .USER
            ),
            currency="EGP",
            unit_label="customer",
            period=(
                FinancialPeriod.MONTHLY
            ),
            rationale="Selling price.",
            profile_fields=[
                "selling_price"
            ],
        )