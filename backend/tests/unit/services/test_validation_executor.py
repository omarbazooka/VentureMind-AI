from unittest.mock import Mock
from uuid import uuid4

import pytest

import app.services.validation_executor as executor
from app.schemas.analysis import AnalysisStage
from app.schemas.validation import (
    ValidationAnalysis,
    ValidationDraft,
    ValidationStatus,
)
from app.schemas.validation_runtime import ValidationStageClaim
from app.services.validation_grounding import ValidationGroundingError


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


def make_claim() -> ValidationStageClaim:
    return ValidationStageClaim.model_construct(
        stage_run_id=uuid4(),
        analysis_run_id=uuid4(),
        stage=AnalysisStage.INDEPENDENT_VALIDATION,
        attempt=1,
        context=object(),
    )


def test_validation_executor_completes_grounded(monkeypatch):
    claim = make_claim()
    draft = ValidationDraft(
        executive_assessment="Draft assessment."
    )
    grounded = ValidationAnalysis(
        status=ValidationStatus.PASSED,
        executive_assessment="Draft assessment.",
        issues=[],
        can_proceed=True,
    )
    persisted = object()

    monkeypatch.setattr(executor, "claim_validation_stage", Mock(return_value=claim))
    monkeypatch.setattr(executor, "validate_grounded_validation_analysis", Mock(return_value=grounded))
    monkeypatch.setattr(executor, "complete_validation_stage", Mock(return_value=persisted))

    session_factory = FakeSessionFactory()
    runner = Mock(return_value=draft)

    result = executor.execute_validation_stage(
        session_factory=session_factory,
        stage_run_id=claim.stage_run_id,
        runner=runner,
    )

    assert result is persisted
    runner.assert_called_once_with(claim.context)


def test_validation_executor_marks_failed_on_grounding_error(monkeypatch):
    claim = make_claim()
    monkeypatch.setattr(executor, "claim_validation_stage", Mock(return_value=claim))
    monkeypatch.setattr(
        executor,
        "validate_grounded_validation_analysis",
        Mock(side_effect=ValidationGroundingError("Fake grounding error")),
    )
    fail_mock = Mock()
    monkeypatch.setattr(executor, "fail_validation_stage", fail_mock)

    session_factory = FakeSessionFactory()
    runner = Mock(return_value=ValidationDraft(executive_assessment="Test assessment string"))

    with pytest.raises(executor.ValidationExecutionError, match="Validation grounding verification failed"):
        executor.execute_validation_stage(
            session_factory=session_factory,
            stage_run_id=claim.stage_run_id,
            runner=runner,
        )

    fail_mock.assert_called_once()
