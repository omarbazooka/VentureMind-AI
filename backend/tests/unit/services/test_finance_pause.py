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
    FinanceInputRequest,
)
from app.services.finance_stage import (
    FinanceStageStateError,
    pause_finance_for_user_input,
)


def make_pause_setup():
    analysis_run_id = uuid4()
    stage_run_id = uuid4()

    stage_run = SimpleNamespace(
        id=stage_run_id,
        analysis_run_id=analysis_run_id,
        stage=AnalysisStage.FINANCE.value,
        status=(
            AnalysisStageStatus
            .RUNNING
            .value
        ),
        error_code="OLD_ERROR",
        error_message="Old error.",
    )

    analysis_run = SimpleNamespace(
        id=analysis_run_id,
        status=(
            AnalysisRunStatus
            .RUNNING
            .value
        ),
        error_code="OLD_ERROR",
        error_message="Old error.",
    )

    db = Mock()

    return (
        db,
        stage_run,
        analysis_run,
    )


def make_request():
    return FinanceInputRequest(
        input_name=(
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
        ),
        question=(
            "What price will you charge "
            "per customer?"
        ),
        currency="EGP",
        unit_label="customer",
    )

def test_pause_finance_creates_pending_input():
    (
        db,
        stage_run,
        analysis_run,
    ) = make_pause_setup()

    db.scalar.side_effect = [
        stage_run,
        analysis_run,
        None,
    ]

    run_input = (
        pause_finance_for_user_input(
            db=db,
            stage_run_id=stage_run.id,
            request=make_request(),
        )
    )

    assert (
        run_input.analysis_run_id
        == analysis_run.id
    )

    assert (
        run_input.stage_run_id
        == stage_run.id
    )

    assert (
        run_input.input_name
        == (
            FinancialInputName
            .SELLING_PRICE_PER_UNIT
            .value
        )
    )

    assert (
        run_input.status
        == AnalysisRunInputStatus
        .PENDING
        .value
    )

    assert (
        run_input.response_data
        is None
    )

    assert (
        run_input.request_data[
            "currency"
        ]
        == "EGP"
    )

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

    assert stage_run.error_code is None
    assert stage_run.error_message is None
    assert analysis_run.error_code is None
    assert analysis_run.error_message is None

    db.add.assert_called_once_with(
        run_input
    )

    db.flush.assert_called_once()

def test_pause_requires_running_finance_stage():
    (
        db,
        stage_run,
        _,
    ) = make_pause_setup()

    stage_run.status = (
        AnalysisStageStatus
        .PENDING
        .value
    )

    db.scalar.return_value = (
        stage_run
    )

    with pytest.raises(
        FinanceStageStateError
    ):
        pause_finance_for_user_input(
            db=db,
            stage_run_id=stage_run.id,
            request=make_request(),
        )

    db.add.assert_not_called()

def test_pause_requires_running_parent_analysis():
    (
        db,
        stage_run,
        analysis_run,
    ) = make_pause_setup()

    analysis_run.status = (
        AnalysisRunStatus
        .PAUSED_FOR_USER
        .value
    )

    db.scalar.side_effect = [
        stage_run,
        analysis_run,
    ]

    with pytest.raises(
        FinanceStageStateError
    ):
        pause_finance_for_user_input(
            db=db,
            stage_run_id=stage_run.id,
            request=make_request(),
        )

    assert (
        stage_run.status
        == AnalysisStageStatus
        .RUNNING
        .value
    )

    db.add.assert_not_called()


def test_pause_rejects_second_pending_input():
    (
        db,
        stage_run,
        analysis_run,
    ) = make_pause_setup()

    existing_pending = (
        SimpleNamespace(
            id=uuid4(),
            status=(
                AnalysisRunInputStatus
                .PENDING
                .value
            ),
        )
    )

    db.scalar.side_effect = [
        stage_run,
        analysis_run,
        existing_pending,
    ]

    with pytest.raises(
        FinanceStageStateError
    ):
        pause_finance_for_user_input(
            db=db,
            stage_run_id=stage_run.id,
            request=make_request(),
        )

    assert (
        stage_run.status
        == AnalysisStageStatus
        .RUNNING
        .value
    )

    assert (
        analysis_run.status
        == AnalysisRunStatus
        .RUNNING
        .value
    )

    db.add.assert_not_called()

def test_pause_rejects_non_finance_stage():
    (
        db,
        stage_run,
        _,
    ) = make_pause_setup()

    stage_run.stage = (
        AnalysisStage
        .BUSINESS_STRATEGY
        .value
    )

    db.scalar.return_value = (
        stage_run
    )

    with pytest.raises(
        FinanceStageStateError
    ):
        pause_finance_for_user_input(
            db=db,
            stage_run_id=stage_run.id,
            request=make_request(),
        )

    db.add.assert_not_called()