from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from app.schemas.analysis import (
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.finance import FinancialScenarioBundle
from app.services.analytics_stage import (
    AnalyticsStageDependencyError,
    AnalyticsStageStateError,
    claim_analytics_stage,
)


def dummy_bundle() -> FinancialScenarioBundle:
    return FinancialScenarioBundle.model_construct(
        base=None,
        upside=None,
        downside=None,
        comparisons=[],
        limitations=[],
    )


def make_setup():
    analysis_run_id = uuid4()
    stage_run = SimpleNamespace(
        id=uuid4(),
        analysis_run_id=analysis_run_id,
        stage=AnalysisStage.DECISION_ANALYTICS.value,
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
    finance_result = SimpleNamespace(
        stage_run_id=uuid4(),
    )
    db = Mock()
    db.scalar.return_value = stage_run
    db.get.return_value = analysis_run
    return db, stage_run, analysis_run, finance_result


def test_claim_analytics_stage_loads_completed_finance_dependency():
    db, stage_run, analysis_run, finance_result = make_setup()
    bundle = dummy_bundle()

    with patch(
        "app.services.analytics_stage._load_completed_finance_result",
        return_value=(finance_result, bundle),
    ):
        claim = claim_analytics_stage(
            db=db,
            stage_run_id=stage_run.id,
        )

    assert claim.stage == AnalysisStage.DECISION_ANALYTICS
    assert claim.analysis_run_id == analysis_run.id
    assert claim.finance_stage_run_id == finance_result.stage_run_id
    assert stage_run.status == AnalysisStageStatus.RUNNING.value
    assert stage_run.started_at is not None
    db.flush.assert_called_once()


def test_claim_analytics_stage_requires_pending_stage():
    db, stage_run, _, _ = make_setup()
    stage_run.status = AnalysisStageStatus.RUNNING.value

    with pytest.raises(AnalyticsStageStateError):
        claim_analytics_stage(
            db=db,
            stage_run_id=stage_run.id,
        )


def test_claim_analytics_stage_preserves_pending_state_when_finance_missing():
    db, stage_run, _, _ = make_setup()

    with patch(
        "app.services.analytics_stage._load_completed_finance_result",
        side_effect=AnalyticsStageDependencyError(
            "Finance result missing"
        ),
    ):
        with pytest.raises(AnalyticsStageDependencyError):
            claim_analytics_stage(
                db=db,
                stage_run_id=stage_run.id,
            )

    assert stage_run.status == AnalysisStageStatus.PENDING.value
