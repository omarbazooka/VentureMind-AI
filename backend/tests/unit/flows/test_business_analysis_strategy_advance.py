from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.flows.business_analysis_flow import (
    BusinessAnalysisFlow,
)
from app.schemas.analysis import (
    AnalysisStage,
    AnalysisStageStatus,
)


def test_advance_strategy_schedules_finance():
    run_id = uuid4()
    strategy_stage_id = uuid4()

    analysis_run = SimpleNamespace(
        id=run_id,
        status="RUNNING",
    )

    strategy_stage = SimpleNamespace(
        id=strategy_stage_id,
        analysis_run_id=run_id,
        stage=(
            AnalysisStage
            .BUSINESS_STRATEGY
            .value
        ),
        attempt=1,
        status=(
            AnalysisStageStatus
            .COMPLETED
            .value
        ),
    )

    strategy_result = SimpleNamespace(
        id=uuid4(),
        analysis_run_id=run_id,
        stage_run_id=strategy_stage_id,
        stage=(
            AnalysisStage
            .BUSINESS_STRATEGY
            .value
        ),
    )

    db = Mock()

    db.scalar.side_effect = [
        analysis_run,
        strategy_stage,
        strategy_result,
        analysis_run,
        None,
    ]

    result = (
        BusinessAnalysisFlow()
        .advance_strategy(
            db=db,
            run_id=run_id,
        )
    )

    assert (
        result.analysis_run_id
        == run_id
    )

    assert (
        result.stage
        == AnalysisStage.FINANCE.value
    )

    assert result.attempt == 1

    assert (
        result.status
        == AnalysisStageStatus
        .PENDING
        .value
    )

    db.add.assert_called_once_with(
        result
    )

    db.flush.assert_called_once()


def test_advance_strategy_reuses_existing_finance():
    run_id = uuid4()
    strategy_stage_id = uuid4()

    analysis_run = SimpleNamespace(
        id=run_id,
        status="RUNNING",
    )

    strategy_stage = SimpleNamespace(
        id=strategy_stage_id,
        status="COMPLETED",
    )

    strategy_result = SimpleNamespace(
        id=uuid4(),
    )

    existing_finance = SimpleNamespace(
        id=uuid4(),
        analysis_run_id=run_id,
        stage=AnalysisStage.FINANCE.value,
        attempt=1,
        status="PENDING",
    )

    db = Mock()

    db.scalar.side_effect = [
        analysis_run,
        strategy_stage,
        strategy_result,
        analysis_run,
        existing_finance,
    ]

    result = (
        BusinessAnalysisFlow()
        .advance_strategy(
            db=db,
            run_id=run_id,
        )
    )

    assert result is existing_finance

    db.add.assert_not_called()
    

import pytest

from app.flows.business_analysis_flow import (
    BusinessAnalysisRunStateError,
)


def test_advance_strategy_requires_completed_strategy():
    run_id = uuid4()

    analysis_run = SimpleNamespace(
        id=run_id,
        status="RUNNING",
    )

    db = Mock()

    db.scalar.side_effect = [
        analysis_run,
        None,
    ]

    with pytest.raises(
        BusinessAnalysisRunStateError
    ):
        (
            BusinessAnalysisFlow()
            .advance_strategy(
                db=db,
                run_id=run_id,
            )
        )

    db.add.assert_not_called()


def test_advance_strategy_requires_persisted_result():
    run_id = uuid4()

    analysis_run = SimpleNamespace(
        id=run_id,
        status="RUNNING",
    )

    strategy_stage = SimpleNamespace(
        id=uuid4(),
        status="COMPLETED",
    )

    db = Mock()

    db.scalar.side_effect = [
        analysis_run,
        strategy_stage,
        None,
    ]

    with pytest.raises(
        BusinessAnalysisRunStateError
    ):
        (
            BusinessAnalysisFlow()
            .advance_strategy(
                db=db,
                run_id=run_id,
            )
        )

    db.add.assert_not_called()

