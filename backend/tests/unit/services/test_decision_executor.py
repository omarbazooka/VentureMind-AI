from unittest.mock import Mock
from uuid import uuid4

import pytest

import app.services.decision_executor as executor
from app.schemas.analysis import AnalysisStage
from app.schemas.decision import (
    DecisionConfidence,
    FinalDecisionAnalysis,
    FinalDecisionDraft,
    VentureDecision,
)
from app.schemas.decision_runtime import DecisionStageClaim
from app.services.decision_grounding import DecisionGroundingError


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


def make_claim() -> DecisionStageClaim:
    return DecisionStageClaim.model_construct(
        stage_run_id=uuid4(),
        analysis_run_id=uuid4(),
        stage=AnalysisStage.INVESTMENT_COMMITTEE,
        attempt=1,
        context=object(),
    )


def test_decision_executor_completes_grounded(monkeypatch):
    claim = make_claim()
    draft = FinalDecisionDraft(
        decision=VentureDecision.GO,
        confidence=DecisionConfidence.HIGH,
        rationale="Sound venture.",
    )
    grounded = FinalDecisionAnalysis(
        decision=VentureDecision.GO,
        confidence=DecisionConfidence.HIGH,
        rationale="Sound venture.",
    )
    persisted = object()

    monkeypatch.setattr(executor, "claim_decision_stage", Mock(return_value=claim))
    monkeypatch.setattr(executor, "validate_grounded_decision", Mock(return_value=grounded))
    monkeypatch.setattr(executor, "complete_decision_stage", Mock(return_value=persisted))

    session_factory = FakeSessionFactory()
    runner = Mock(return_value=draft)

    result = executor.execute_decision_stage(
        session_factory=session_factory,
        stage_run_id=claim.stage_run_id,
        runner=runner,
    )

    assert result is persisted
    runner.assert_called_once_with(claim.context)


def test_decision_executor_marks_failed_on_grounding_error(monkeypatch):
    claim = make_claim()
    monkeypatch.setattr(executor, "claim_decision_stage", Mock(return_value=claim))
    monkeypatch.setattr(
        executor,
        "validate_grounded_decision",
        Mock(side_effect=DecisionGroundingError("Fake error")),
    )
    fail_mock = Mock()
    monkeypatch.setattr(executor, "fail_decision_stage", fail_mock)

    session_factory = FakeSessionFactory()
    runner = Mock(
        return_value=FinalDecisionDraft(
            decision=VentureDecision.GO,
            confidence=DecisionConfidence.LOW,
            rationale="Detailed rationale text",
        )
    )

    with pytest.raises(executor.DecisionExecutionError, match="Investment Committee grounding verification failed"):
        executor.execute_decision_stage(
            session_factory=session_factory,
            stage_run_id=claim.stage_run_id,
            runner=runner,
        )

    fail_mock.assert_called_once()
