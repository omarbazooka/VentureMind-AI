from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.flows.business_analysis_flow import (
    BusinessAnalysisFlow,
    BusinessAnalysisRunStateError,
)
from app.schemas.analysis import (
    AnalysisStage,
    AnalysisStageStatus,
)


def make_completed_finance(run_id):
    finance_stage_id = uuid4()
    finance_stage = SimpleNamespace(
        id=finance_stage_id,
        analysis_run_id=run_id,
        stage=AnalysisStage.FINANCE.value,
        attempt=1,
        status=AnalysisStageStatus.COMPLETED.value,
    )
    finance_result = SimpleNamespace(
        id=uuid4(),
        analysis_run_id=run_id,
        stage_run_id=finance_stage_id,
        stage=AnalysisStage.FINANCE.value,
    )
    return finance_stage, finance_result


def test_advance_finance_schedules_decision_analytics():
    run_id = uuid4()
    analysis_run = SimpleNamespace(id=run_id, status="RUNNING")
    finance_stage, finance_result = make_completed_finance(run_id)
    db = Mock()
    db.scalar.side_effect = [
        analysis_run,
        finance_stage,
        finance_result,
        analysis_run,
        None,
    ]

    result = BusinessAnalysisFlow().advance_finance(
        db=db,
        run_id=run_id,
    )

    assert result.analysis_run_id == run_id
    assert result.stage == AnalysisStage.DECISION_ANALYTICS.value
    assert result.attempt == 1
    assert result.status == AnalysisStageStatus.PENDING.value
    db.add.assert_called_once_with(result)
    db.flush.assert_called_once()


def test_advance_finance_reuses_existing_decision_analytics_stage():
    run_id = uuid4()
    analysis_run = SimpleNamespace(id=run_id, status="RUNNING")
    finance_stage, finance_result = make_completed_finance(run_id)
    existing_analytics = SimpleNamespace(
        id=uuid4(),
        analysis_run_id=run_id,
        stage=AnalysisStage.DECISION_ANALYTICS.value,
        attempt=1,
        status=AnalysisStageStatus.PENDING.value,
    )
    db = Mock()
    db.scalar.side_effect = [
        analysis_run,
        finance_stage,
        finance_result,
        analysis_run,
        existing_analytics,
    ]

    result = BusinessAnalysisFlow().advance_finance(
        db=db,
        run_id=run_id,
    )

    assert result is existing_analytics
    db.add.assert_not_called()


def test_advance_finance_requires_completed_finance_stage():
    run_id = uuid4()
    analysis_run = SimpleNamespace(id=run_id, status="RUNNING")
    db = Mock()
    db.scalar.side_effect = [analysis_run, None]

    with pytest.raises(BusinessAnalysisRunStateError):
        BusinessAnalysisFlow().advance_finance(
            db=db,
            run_id=run_id,
        )

    db.add.assert_not_called()


def test_advance_finance_requires_persisted_finance_result():
    run_id = uuid4()
    analysis_run = SimpleNamespace(id=run_id, status="RUNNING")
    finance_stage, _ = make_completed_finance(run_id)
    db = Mock()
    db.scalar.side_effect = [
        analysis_run,
        finance_stage,
        None,
    ]

    with pytest.raises(BusinessAnalysisRunStateError):
        BusinessAnalysisFlow().advance_finance(
            db=db,
            run_id=run_id,
        )

    db.add.assert_not_called()
