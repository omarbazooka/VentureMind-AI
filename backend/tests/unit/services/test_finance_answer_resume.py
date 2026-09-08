from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.schemas.analysis import (
    AnalysisRunInputStatus,
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.finance import (
    FinancialInputName,
)
from app.schemas.finance_runtime import (
    FinanceInputOption,
    FinanceInputOptionBasis,
    FinanceInputRequest,
    FinanceUserAnswerMode,
    FinanceUserInputAnswer,
    ResolvedFinanceUserInput,
)
from app.services.finance_stage import (
    FinanceStageStateError,
    answer_finance_user_input,
)


def _make_state(
    *,
    request: FinanceInputRequest,
):
    analysis_run_id = uuid4()
    stage_run_id = uuid4()
    run_input_id = uuid4()

    run_input = SimpleNamespace(
        id=run_input_id,
        analysis_run_id=analysis_run_id,
        stage_run_id=stage_run_id,
        input_name=request.input_name.value,
        status=AnalysisRunInputStatus.PENDING.value,
        request_data=request.model_dump(mode="json"),
        response_data=None,
        source_message_id=None,
        answered_at=None,
    )

    stage_run = SimpleNamespace(
        id=stage_run_id,
        analysis_run_id=analysis_run_id,
        stage=AnalysisStage.FINANCE.value,
        status=(
            AnalysisStageStatus
            .PAUSED_FOR_USER
            .value
        ),
        error_code=None,
        error_message=None,
    )

    analysis_run = SimpleNamespace(
        id=analysis_run_id,
        status=(
            AnalysisRunStatus
            .PAUSED_FOR_USER
            .value
        ),
        error_code=None,
        error_message=None,
    )

    db = Mock()
    db.scalar.side_effect = [
        run_input,
        stage_run,
        analysis_run,
    ]

    return (
        db,
        run_input,
        stage_run,
        analysis_run,
    )


def test_custom_answer_is_persisted_and_ready_to_reclaim():
    request = FinanceInputRequest(
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        question="Which price should we model?",
        currency="EGP",
        unit_label="customer",
    )
    (
        db,
        run_input,
        stage_run,
        analysis_run,
    ) = _make_state(request=request)

    answer = FinanceUserInputAnswer(
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        answer_mode=FinanceUserAnswerMode.CUSTOM,
        value=Decimal("350"),
        currency="EGP",
        unit_label="customer",
    )

    result = answer_finance_user_input(
        db=db,
        run_input_id=run_input.id,
        answer=answer,
    )

    resolved = ResolvedFinanceUserInput.model_validate(
        result.response_data
    )

    assert resolved.value == Decimal("350")
    assert (
        resolved.answer_mode
        == FinanceUserAnswerMode.CUSTOM
    )
    assert (
        result.status
        == AnalysisRunInputStatus.ANSWERED.value
    )
    assert result.answered_at is not None
    assert (
        stage_run.status
        == AnalysisStageStatus.PENDING.value
    )
    assert (
        analysis_run.status
        == AnalysisRunStatus.RUNNING.value
    )
    db.flush.assert_called_once()


def test_selected_option_uses_persisted_option_value():
    option = FinanceInputOption(
        option_id="market_midpoint",
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        label="Market midpoint",
        value=Decimal("300"),
        currency="EGP",
        unit_label="customer",
        basis=(
            FinanceInputOptionBasis
            .CALCULATED_FROM_WEB
        ),
        rationale="Deterministic midpoint.",
        supporting_stages=[
            AnalysisStage.COMPETITOR_INTELLIGENCE
        ],
        evidence_source_ids=["source-1"],
        calculation_basis="(200 + 400) / 2",
    )
    request = FinanceInputRequest(
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        question="Which price should we model?",
        options=[option],
        currency="EGP",
        unit_label="customer",
    )
    (
        db,
        run_input,
        _,
        _,
    ) = _make_state(request=request)

    answer = FinanceUserInputAnswer(
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        answer_mode=(
            FinanceUserAnswerMode.SELECTED_OPTION
        ),
        selected_option_id="market_midpoint",
    )

    result = answer_finance_user_input(
        db=db,
        run_input_id=run_input.id,
        answer=answer,
    )

    resolved = ResolvedFinanceUserInput.model_validate(
        result.response_data
    )

    assert resolved.value == Decimal("300")
    assert resolved.currency == "EGP"
    assert resolved.unit_label == "customer"
    assert (
        resolved.selected_option_id
        == "market_midpoint"
    )


def test_custom_answer_must_match_request_currency():
    request = FinanceInputRequest(
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        question="Which price should we model?",
        currency="EGP",
        unit_label="customer",
    )
    (
        db,
        run_input,
        stage_run,
        analysis_run,
    ) = _make_state(request=request)

    answer = FinanceUserInputAnswer(
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        answer_mode=FinanceUserAnswerMode.CUSTOM,
        value=Decimal("350"),
        currency="USD",
        unit_label="customer",
    )

    with pytest.raises(FinanceStageStateError):
        answer_finance_user_input(
            db=db,
            run_input_id=run_input.id,
            answer=answer,
        )

    assert (
        run_input.status
        == AnalysisRunInputStatus.PENDING.value
    )
    assert run_input.response_data is None
    assert (
        stage_run.status
        == AnalysisStageStatus
        .PAUSED_FOR_USER
        .value
    )
    assert (
        analysis_run.status
        == AnalysisRunStatus
        .PAUSED_FOR_USER
        .value
    )
    db.flush.assert_not_called()


def test_answer_rejects_unknown_selected_option():
    request = FinanceInputRequest(
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        question="Which price should we model?",
        currency="EGP",
        unit_label="customer",
    )
    (
        db,
        run_input,
        _,
        _,
    ) = _make_state(request=request)

    answer = FinanceUserInputAnswer(
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        answer_mode=(
            FinanceUserAnswerMode.SELECTED_OPTION
        ),
        selected_option_id="does-not-exist",
    )

    with pytest.raises(FinanceStageStateError):
        answer_finance_user_input(
            db=db,
            run_input_id=run_input.id,
            answer=answer,
        )

    db.flush.assert_not_called()
