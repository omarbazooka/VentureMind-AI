from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from app.schemas.analysis import (
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.risk_runtime import RiskAnalysisContext
from app.services.risk_stage import (
    RiskStageDependencyError,
    RiskStageStateError,
    claim_risk_stage,
)


def make_setup():
    analysis_run_id = uuid4()
    stage_run = SimpleNamespace(
        id=uuid4(),
        analysis_run_id=analysis_run_id,
        stage=AnalysisStage.RISK.value,
        attempt=1,
        status=AnalysisStageStatus.PENDING.value,
        started_at=None,
        error_code=None,
        error_message=None,
    )
    analysis_run = SimpleNamespace(
        id=analysis_run_id,
        status=AnalysisRunStatus.RUNNING.value,
    )
    db = Mock()
    db.scalar.return_value = stage_run
    db.get.return_value = analysis_run
    return db, stage_run, analysis_run


def test_claim_risk_stage_builds_context_before_running():
    db, stage_run, analysis_run = make_setup()
    context = RiskAnalysisContext.model_construct()

    with patch(
        "app.services.risk_stage._build_context",
        return_value=context,
    ):
        claim = claim_risk_stage(
            db=db,
            stage_run_id=stage_run.id,
        )

    assert claim.stage == AnalysisStage.RISK
    assert claim.analysis_run_id == analysis_run.id
    assert claim.context is context
    assert stage_run.status == AnalysisStageStatus.RUNNING.value
    assert stage_run.started_at is not None
    db.flush.assert_called_once()


def test_claim_risk_stage_requires_pending_state():
    db, stage_run, _ = make_setup()
    stage_run.status = AnalysisStageStatus.RUNNING.value

    with pytest.raises(RiskStageStateError):
        claim_risk_stage(
            db=db,
            stage_run_id=stage_run.id,
        )


def test_claim_risk_stage_keeps_pending_when_context_is_missing():
    db, stage_run, _ = make_setup()

    with patch(
        "app.services.risk_stage._build_context",
        side_effect=RiskStageDependencyError(
            "missing upstream context"
        ),
    ):
        with pytest.raises(RiskStageDependencyError):
            claim_risk_stage(
                db=db,
                stage_run_id=stage_run.id,
            )

    assert stage_run.status == AnalysisStageStatus.PENDING.value
