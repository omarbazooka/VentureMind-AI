from decimal import Decimal
from uuid import uuid4

import pytest

from app.models.analysis_run_input import (
    AnalysisRunInput,
)
from app.schemas.analysis import (
    AnalysisRunInputStatus,
)
from app.schemas.finance import (
    FinancialAssumption,
    FinancialAssumptionProvenance,
    FinancialAssumptionSet,
    FinancialInputName,
    FinancialPeriod,
    FinancialScenarioInputs,
    FinancialScenarioKind,
)
from app.schemas.finance_runtime import (
    FinanceUserAnswerMode,
    ResolvedFinanceUserInput,
)
from app.services.finance_run_inputs import (
    FinanceRunInputGroundingError,
    apply_answered_finance_inputs,
)


def _assumption(
    *,
    input_name: FinancialInputName,
    value: Decimal | None,
    currency: str | None = None,
    unit_label: str | None = None,
    period: FinancialPeriod | None = None,
) -> FinancialAssumption:
    return FinancialAssumption(
        input_name=input_name,
        value=value,
        provenance=(
            FinancialAssumptionProvenance
            .AI_ASSUMPTION
            if value is not None
            else None
        ),
        currency=currency,
        unit_label=unit_label,
        period=period,
        rationale="Test assumption.",
    )


def _scenario(
    scenario: FinancialScenarioKind,
) -> FinancialAssumptionSet:
    return FinancialAssumptionSet(
        scenario=scenario,
        selling_price_per_unit=_assumption(
            input_name=(
                FinancialInputName
                .SELLING_PRICE_PER_UNIT
            ),
            value=None,
            currency="EGP",
            unit_label="customer",
        ),
        sales_volume=_assumption(
            input_name=(
                FinancialInputName.SALES_VOLUME
            ),
            value=Decimal("100"),
            unit_label="customer",
            period=FinancialPeriod.MONTHLY,
        ),
        variable_cost_per_unit=_assumption(
            input_name=(
                FinancialInputName
                .VARIABLE_COST_PER_UNIT
            ),
            value=Decimal("50"),
            currency="EGP",
            unit_label="customer",
        ),
        fixed_costs=_assumption(
            input_name=(
                FinancialInputName.FIXED_COSTS
            ),
            value=Decimal("10000"),
            currency="EGP",
            period=FinancialPeriod.MONTHLY,
        ),
    )


def _inputs() -> FinancialScenarioInputs:
    return FinancialScenarioInputs(
        base=_scenario(
            FinancialScenarioKind.BASE
        ),
        upside=_scenario(
            FinancialScenarioKind.UPSIDE
        ),
        downside=_scenario(
            FinancialScenarioKind.DOWNSIDE
        ),
    )


def _answered_input(
    *,
    analysis_run_id,
    stage_run_id,
    value: str,
) -> AnalysisRunInput:
    resolved = ResolvedFinanceUserInput(
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        answer_mode=FinanceUserAnswerMode.CUSTOM,
        value=Decimal(value),
        currency="EGP",
        unit_label="customer",
    )

    return AnalysisRunInput(
        id=uuid4(),
        analysis_run_id=analysis_run_id,
        stage_run_id=stage_run_id,
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
            .value
        ),
        status=(
            AnalysisRunInputStatus.ANSWERED.value
        ),
        request_data={},
        response_data=resolved.model_dump(
            mode="json"
        ),
    )


def test_answered_input_overrides_all_scenarios_as_user_value():
    analysis_run_id = uuid4()
    stage_run_id = uuid4()
    run_input = _answered_input(
        analysis_run_id=analysis_run_id,
        stage_run_id=stage_run_id,
        value="350",
    )

    result = apply_answered_finance_inputs(
        inputs=_inputs(),
        run_inputs=[run_input],
        analysis_run_id=analysis_run_id,
        stage_run_id=stage_run_id,
    )

    for scenario in (
        result.base,
        result.upside,
        result.downside,
    ):
        assumption = (
            scenario.selling_price_per_unit
        )
        assert assumption.value == Decimal("350")
        assert (
            assumption.provenance
            == FinancialAssumptionProvenance.USER
        )
        assert assumption.profile_fields == []
        assert assumption.analysis_run_input_ids == [
            run_input.id
        ]


def test_latest_answered_value_wins_deterministically():
    analysis_run_id = uuid4()
    stage_run_id = uuid4()
    first = _answered_input(
        analysis_run_id=analysis_run_id,
        stage_run_id=stage_run_id,
        value="300",
    )
    second = _answered_input(
        analysis_run_id=analysis_run_id,
        stage_run_id=stage_run_id,
        value="350",
    )

    result = apply_answered_finance_inputs(
        inputs=_inputs(),
        run_inputs=[first, second],
        analysis_run_id=analysis_run_id,
        stage_run_id=stage_run_id,
    )

    assert (
        result.base
        .selling_price_per_unit
        .value
        == Decimal("350")
    )
    assert (
        result.base
        .selling_price_per_unit
        .analysis_run_input_ids
        == [second.id]
    )


def test_run_input_from_other_analysis_is_rejected():
    analysis_run_id = uuid4()
    stage_run_id = uuid4()
    run_input = _answered_input(
        analysis_run_id=uuid4(),
        stage_run_id=stage_run_id,
        value="350",
    )

    with pytest.raises(
        FinanceRunInputGroundingError
    ):
        apply_answered_finance_inputs(
            inputs=_inputs(),
            run_inputs=[run_input],
            analysis_run_id=analysis_run_id,
            stage_run_id=stage_run_id,
        )


def test_pending_run_input_cannot_be_grounded():
    analysis_run_id = uuid4()
    stage_run_id = uuid4()
    run_input = _answered_input(
        analysis_run_id=analysis_run_id,
        stage_run_id=stage_run_id,
        value="350",
    )
    run_input.status = (
        AnalysisRunInputStatus.PENDING.value
    )

    with pytest.raises(
        FinanceRunInputGroundingError
    ):
        apply_answered_finance_inputs(
            inputs=_inputs(),
            run_inputs=[run_input],
            analysis_run_id=analysis_run_id,
            stage_run_id=stage_run_id,
        )
