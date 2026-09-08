from unittest.mock import Mock
from uuid import uuid4

import pytest

import app.services.analytics_executor as executor
from app.schemas.analysis import AnalysisStage
from app.schemas.analytics import DecisionAnalyticsResult
from app.schemas.analytics_runtime import AnalyticsStageClaim


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


def make_claim() -> AnalyticsStageClaim:
    return AnalyticsStageClaim.model_construct(
        stage_run_id=uuid4(),
        analysis_run_id=uuid4(),
        stage=AnalysisStage.DECISION_ANALYTICS,
        attempt=1,
        finance_stage_run_id=uuid4(),
        finance_bundle=object(),
    )


def make_result(claim: AnalyticsStageClaim) -> DecisionAnalyticsResult:
    return DecisionAnalyticsResult(
        finance_stage_run_id=claim.finance_stage_run_id,
    )


def test_executor_completes_decision_analytics(monkeypatch):
    claim = make_claim()
    analytics_result = make_result(claim)
    persisted_result = object()

    monkeypatch.setattr(
        executor,
        "claim_analytics_stage",
        Mock(return_value=claim),
    )
    builder_mock = Mock(return_value=analytics_result)
    monkeypatch.setattr(
        executor,
        "build_decision_analytics_result",
        builder_mock,
    )
    complete_mock = Mock(return_value=persisted_result)
    monkeypatch.setattr(
        executor,
        "complete_analytics_stage",
        complete_mock,
    )
    fail_mock = Mock()
    monkeypatch.setattr(
        executor,
        "fail_analytics_stage",
        fail_mock,
    )

    session_factory = FakeSessionFactory()
    result = executor.execute_decision_analytics_stage(
        session_factory=session_factory,
        stage_run_id=claim.stage_run_id,
    )

    assert result is persisted_result
    builder_mock.assert_called_once_with(
        finance_stage_run_id=claim.finance_stage_run_id,
        finance_bundle=claim.finance_bundle,
    )
    complete_mock.assert_called_once()
    fail_mock.assert_not_called()
    assert len(session_factory.sessions) == 2
    assert session_factory.sessions[0].commit_count == 1
    assert session_factory.sessions[1].commit_count == 1


def test_executor_marks_calculation_failure(monkeypatch):
    claim = make_claim()
    monkeypatch.setattr(
        executor,
        "claim_analytics_stage",
        Mock(return_value=claim),
    )
    monkeypatch.setattr(
        executor,
        "build_decision_analytics_result",
        Mock(side_effect=executor.DecisionSensitivityError("bad sensitivity")),
    )
    fail_mock = Mock()
    monkeypatch.setattr(
        executor,
        "fail_analytics_stage",
        fail_mock,
    )

    session_factory = FakeSessionFactory()

    with pytest.raises(executor.AnalyticsExecutionError):
        executor.execute_decision_analytics_stage(
            session_factory=session_factory,
            stage_run_id=claim.stage_run_id,
        )

    fail_mock.assert_called_once()
    assert fail_mock.call_args.kwargs["error_code"] == (
        "DECISION_ANALYTICS_CALCULATION_ERROR"
    )
