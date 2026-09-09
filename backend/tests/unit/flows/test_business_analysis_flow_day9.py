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
from app.schemas.validation import ValidationAnalysis, ValidationStatus


def make_completed_stage(run_id, stage: AnalysisStage):
    stage_id = uuid4()
    stage_run = SimpleNamespace(
        id=stage_id,
        analysis_run_id=run_id,
        stage=stage.value,
        attempt=1,
        status=AnalysisStageStatus.COMPLETED.value,
    )
    result = SimpleNamespace(
        id=uuid4(),
        analysis_run_id=run_id,
        stage_run_id=stage_id,
        stage=stage.value,
        result_data={},
    )
    return stage_run, result


def test_advance_risk_schedules_validation():
    run_id = uuid4()
    analysis_run = SimpleNamespace(id=run_id, status="RUNNING")
    risk_stage, risk_result = make_completed_stage(run_id, AnalysisStage.RISK)
    db = Mock()
    db.scalar.side_effect = [
        analysis_run,
        risk_stage,
        risk_result,
        analysis_run,
        None,  # No existing validation stage
    ]

    result = BusinessAnalysisFlow().advance_risk(db=db, run_id=run_id)

    assert result.analysis_run_id == run_id
    assert result.stage == AnalysisStage.INDEPENDENT_VALIDATION.value
    assert result.attempt == 1
    assert result.status == AnalysisStageStatus.PENDING.value
    db.add.assert_called_once_with(result)


def test_advance_validation_schedules_investment_committee():
    run_id = uuid4()
    analysis_run = SimpleNamespace(id=run_id, status="RUNNING")
    val_stage, val_result = make_completed_stage(run_id, AnalysisStage.INDEPENDENT_VALIDATION)
    val_result.result_data = ValidationAnalysis(
        status=ValidationStatus.PASSED,
        executive_assessment="All clean",
        can_proceed=True,
    ).model_dump(mode="json")

    db = Mock()
    db.scalar.side_effect = [
        analysis_run,
        val_stage,
        val_result,
        analysis_run,
        None,  # No existing investment committee stage
    ]

    result = BusinessAnalysisFlow().advance_validation(db=db, run_id=run_id)

    assert result.analysis_run_id == run_id
    assert result.stage == AnalysisStage.INVESTMENT_COMMITTEE.value
    assert result.attempt == 1
    assert result.status == AnalysisStageStatus.PENDING.value
    db.add.assert_called_once_with(result)


def test_advance_validation_rejects_unsuccessful_validation():
    run_id = uuid4()
    analysis_run = SimpleNamespace(id=run_id, status="RUNNING")
    val_stage, val_result = make_completed_stage(run_id, AnalysisStage.INDEPENDENT_VALIDATION)
    val_result.result_data = ValidationAnalysis(
        status=ValidationStatus.FAILED,
        executive_assessment="Critical flaw found",
        can_proceed=False,
    ).model_dump(mode="json")

    db = Mock()
    db.scalar.side_effect = [
        analysis_run,
        val_stage,
        val_result,
    ]

    with pytest.raises(BusinessAnalysisRunStateError, match="Validation failed and does not permit proceeding"):
        BusinessAnalysisFlow().advance_validation(db=db, run_id=run_id)


def test_advance_validation_schedules_bounded_targeted_retry():
    run_id = uuid4()
    analysis_run = SimpleNamespace(id=run_id, status="RUNNING")
    val_stage, val_result = make_completed_stage(run_id, AnalysisStage.INDEPENDENT_VALIDATION)
    val_result.result_data = ValidationAnalysis(
        status=ValidationStatus.FAILED,
        executive_assessment="Critical flaw in finance modeling",
        can_proceed=False,
        retry_stages=[AnalysisStage.FINANCE],
    ).model_dump(mode="json")

    db = Mock()
    db.scalar.side_effect = [
        analysis_run,
        val_stage,
        val_result,
    ]
    # Mock previous stage_run attempt = 1
    prev_finance = SimpleNamespace(attempt=1)
    db.scalars.return_value.all.return_value = [prev_finance]

    result = BusinessAnalysisFlow().advance_validation(db=db, run_id=run_id)

    assert result.analysis_run_id == run_id
    assert result.stage == AnalysisStage.FINANCE.value
    assert result.attempt == 2
    assert result.status == AnalysisStageStatus.PENDING.value
    db.add.assert_called_once_with(result)
