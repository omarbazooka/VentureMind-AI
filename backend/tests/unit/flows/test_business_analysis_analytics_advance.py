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


def make_completed_analytics(run_id):
    analytics_stage_id = uuid4()
    analytics_stage = SimpleNamespace(
        id=analytics_stage_id,
        analysis_run_id=run_id,
        stage=AnalysisStage.DECISION_ANALYTICS.value,
        attempt=1,
        status=AnalysisStageStatus.COMPLETED.value,
    )
    analytics_result = SimpleNamespace(
        id=uuid4(),
        analysis_run_id=run_id,
        stage_run_id=analytics_stage_id,
        stage=AnalysisStage.DECISION_ANALYTICS.value,
    )
    return analytics_stage, analytics_result


def test_advance_analytics_schedules_risk():
    run_id = uuid4()
    analysis_run = SimpleNamespace(id=run_id, status="RUNNING")
    analytics_stage, analytics_result = make_completed_analytics(run_id)
    db = Mock()
    db.scalar.side_effect = [
        analysis_run,
        analytics_stage,
        analytics_result,
        analysis_run,
        None,
    ]

    result = BusinessAnalysisFlow().advance_analytics(
        db=db,
        run_id=run_id,
    )

    assert result.analysis_run_id == run_id
    assert result.stage == AnalysisStage.RISK.value
    assert result.attempt == 1
    assert result.status == AnalysisStageStatus.PENDING.value
    db.add.assert_called_once_with(result)
    db.flush.assert_called_once()


def test_advance_analytics_reuses_existing_risk_stage():
    run_id = uuid4()
    analysis_run = SimpleNamespace(id=run_id, status="RUNNING")
    analytics_stage, analytics_result = make_completed_analytics(run_id)
    existing_risk = SimpleNamespace(
        id=uuid4(),
        analysis_run_id=run_id,
        stage=AnalysisStage.RISK.value,
        attempt=1,
        status=AnalysisStageStatus.PENDING.value,
    )
    db = Mock()
    db.scalar.side_effect = [
        analysis_run,
        analytics_stage,
        analytics_result,
        analysis_run,
        existing_risk,
    ]

    result = BusinessAnalysisFlow().advance_analytics(
        db=db,
        run_id=run_id,
    )

    assert result is existing_risk
    db.add.assert_not_called()


def test_advance_analytics_requires_completed_analytics_stage():
    run_id = uuid4()
    analysis_run = SimpleNamespace(id=run_id, status="RUNNING")
    db = Mock()
    db.scalar.side_effect = [analysis_run, None]

    with pytest.raises(BusinessAnalysisRunStateError):
        BusinessAnalysisFlow().advance_analytics(
            db=db,
            run_id=run_id,
        )

    db.add.assert_not_called()


def test_advance_analytics_requires_persisted_analytics_result():
    run_id = uuid4()
    analysis_run = SimpleNamespace(id=run_id, status="RUNNING")
    analytics_stage, _ = make_completed_analytics(run_id)
    db = Mock()
    db.scalar.side_effect = [
        analysis_run,
        analytics_stage,
        None,
    ]

    with pytest.raises(BusinessAnalysisRunStateError):
        BusinessAnalysisFlow().advance_analytics(
            db=db,
            run_id=run_id,
        )

    db.add.assert_not_called()
