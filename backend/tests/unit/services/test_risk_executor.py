from unittest.mock import Mock
from uuid import uuid4

import pytest

import app.services.risk_executor as executor
from app.schemas.analysis import AnalysisStage
from app.schemas.risk import RiskAnalysis, RiskDraftAnalysis
from app.schemas.risk_runtime import RiskStageClaim
from app.services.risk_grounding import RiskGroundingError


class FakeSession:
    def __init__(self) -> None:
        self.commit_count = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def commit(self) -> None:
        self.commit_count += 1


class FakeSessionFactory:
    def __init__(self) -> None:
        self.sessions = []

    def __call__(self) -> FakeSession:
        session = FakeSession()
        self.sessions.append(session)
        return session


def make_claim() -> RiskStageClaim:
    return RiskStageClaim.model_construct(
        stage_run_id=uuid4(),
        analysis_run_id=uuid4(),
        stage=AnalysisStage.RISK,
        attempt=1,
        context=object(),
    )


def test_executor_completes_grounded_risk(monkeypatch):
    claim = make_claim()
    draft = RiskDraftAnalysis(
        executive_summary="Draft risk summary."
    )
    grounded = RiskAnalysis(
        executive_summary="Draft risk summary.",
        risks=[],
        overall_level=None,
    )
    persisted = object()

    monkeypatch.setattr(
        executor,
        "claim_risk_stage",
        Mock(return_value=claim),
    )
    runner = Mock(return_value=draft)
    finalize_mock = Mock(return_value=grounded)
    monkeypatch.setattr(
        executor,
        "finalize_risk_analysis",
        finalize_mock,
    )
    complete_mock = Mock(return_value=persisted)
    monkeypatch.setattr(
        executor,
        "complete_risk_stage",
        complete_mock,
    )
    fail_mock = Mock()
    monkeypatch.setattr(
        executor,
        "fail_risk_stage",
        fail_mock,
    )

    session_factory = FakeSessionFactory()
    result = executor.execute_risk_stage(
        session_factory=session_factory,
        stage_run_id=claim.stage_run_id,
        runner=runner,
    )

    assert result is persisted
    runner.assert_called_once_with(claim.context)
    finalize_mock.assert_called_once_with(
        draft=draft,
        context=claim.context,
    )
    complete_mock.assert_called_once()
    fail_mock.assert_not_called()
    assert len(session_factory.sessions) == 2


def test_executor_marks_grounding_failure(monkeypatch):
    claim = make_claim()
    monkeypatch.setattr(
        executor,
        "claim_risk_stage",
        Mock(return_value=claim),
    )
    runner = Mock(
        return_value=RiskDraftAnalysis(
            executive_summary="Draft risk summary."
        )
    )
    monkeypatch.setattr(
        executor,
        "finalize_risk_analysis",
        Mock(
            side_effect=RiskGroundingError(
                "hallucinated lineage"
            )
        ),
    )
    fail_mock = Mock()
    monkeypatch.setattr(
        executor,
        "fail_risk_stage",
        fail_mock,
    )

    with pytest.raises(executor.RiskExecutionError):
        executor.execute_risk_stage(
            session_factory=FakeSessionFactory(),
            stage_run_id=claim.stage_run_id,
            runner=runner,
        )

    fail_mock.assert_called_once()
    assert fail_mock.call_args.kwargs["error_code"] == (
        "INVALID_RISK_GROUNDING"
    )
