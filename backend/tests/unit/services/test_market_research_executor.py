from unittest.mock import Mock
from uuid import uuid4

import pytest

import app.services.market_research_executor as executor

from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
)
from app.schemas.intake import (
    ProfileReadinessStatus,
)
from app.schemas.research import (
    MarketAnalysis,
    ResearchEvidenceQuality,
    ResearchStageClaim,
)
from app.services.market_research_executor import (
    MarketResearchExecutionError,
)


class FakeSession:
    def __init__(self) -> None:
        self.commit_count = 0

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
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


def make_claim(
    *,
    stage: AnalysisStage = (
        AnalysisStage.MARKET_RESEARCH
    ),
) -> ResearchStageClaim:
    return ResearchStageClaim(
        stage_run_id=uuid4(),
        analysis_run_id=uuid4(),
        stage=stage,
        attempt=1,
        profile_snapshot=(
            AnalysisProfileSnapshot(
                readiness=(
                    ProfileReadinessStatus
                    .READY_FOR_ANALYSIS
                ),
                profile_data={
                    "idea_description": (
                        "Gym management SaaS"
                    ),
                    "target_customers": [
                        "Independent gym owners"
                    ],
                    "target_country": "Egypt",
                },
                profile_metadata={},
                unknown_fields=[],
            )
        ),
    )


def make_market_result() -> MarketAnalysis:
    return MarketAnalysis(
        summary=(
            "Reliable market evidence "
            "is not available yet."
        ),
        findings=[],
        evidence_sources=[],
        evidence_quality=(
            ResearchEvidenceQuality
            .INSUFFICIENT
        ),
        limitations=[
            "No external research "
            "was performed in this test."
        ],
    )


def test_executor_completes_market_stage(
    monkeypatch,
):
    claim = make_claim()
    market_result = make_market_result()

    persisted_result = object()

    claim_mock = Mock(
        return_value=claim
    )

    complete_mock = Mock(
        return_value=persisted_result
    )

    fail_mock = Mock()

    monkeypatch.setattr(
        executor,
        "claim_research_stage",
        claim_mock,
    )

    monkeypatch.setattr(
        executor,
        "complete_research_stage",
        complete_mock,
    )

    monkeypatch.setattr(
        executor,
        "fail_research_stage",
        fail_mock,
    )

    runner = Mock(
        return_value=market_result
    )

    session_factory = (
        FakeSessionFactory()
    )

    result = (
        executor
        .execute_market_research_stage(
            session_factory=session_factory,
            stage_run_id=claim.stage_run_id,
            runner=runner,
        )
    )

    assert result is persisted_result

    runner.assert_called_once_with(
        claim
    )

    complete_mock.assert_called_once()

    fail_mock.assert_not_called()

    assert len(
        session_factory.sessions
    ) == 2

    assert (
        session_factory
        .sessions[0]
        .commit_count
        == 1
    )

    assert (
        session_factory
        .sessions[1]
        .commit_count
        == 1
    )


def test_executor_marks_stage_failed_when_runner_fails(
    monkeypatch,
):
    claim = make_claim()

    monkeypatch.setattr(
        executor,
        "claim_research_stage",
        Mock(return_value=claim),
    )

    complete_mock = Mock()

    monkeypatch.setattr(
        executor,
        "complete_research_stage",
        complete_mock,
    )

    fail_mock = Mock()

    monkeypatch.setattr(
        executor,
        "fail_research_stage",
        fail_mock,
    )

    runner = Mock(
        side_effect=TimeoutError(
            "provider timeout"
        )
    )

    session_factory = (
        FakeSessionFactory()
    )

    with pytest.raises(
        MarketResearchExecutionError
    ):
        executor.execute_market_research_stage(
            session_factory=session_factory,
            stage_run_id=claim.stage_run_id,
            runner=runner,
        )

    complete_mock.assert_not_called()

    fail_mock.assert_called_once()

    assert (
        fail_mock.call_args.kwargs[
            "error_code"
        ]
        == "MARKET_RESEARCH_EXECUTION_ERROR"
    )

    assert len(
        session_factory.sessions
    ) == 2

    assert (
        session_factory
        .sessions[0]
        .commit_count
        == 1
    )

    assert (
        session_factory
        .sessions[1]
        .commit_count
        == 1
    )


def test_executor_marks_invalid_result_failed(
    monkeypatch,
):
    claim = make_claim()

    monkeypatch.setattr(
        executor,
        "claim_research_stage",
        Mock(return_value=claim),
    )

    monkeypatch.setattr(
        executor,
        "complete_research_stage",
        Mock(
            side_effect=(
                executor
                .ResearchStageResultValidationError(
                    "invalid result"
                )
            )
        ),
    )

    fail_mock = Mock()

    monkeypatch.setattr(
        executor,
        "fail_research_stage",
        fail_mock,
    )

    session_factory = (
        FakeSessionFactory()
    )

    with pytest.raises(
        MarketResearchExecutionError
    ):
        executor.execute_market_research_stage(
            session_factory=session_factory,
            stage_run_id=claim.stage_run_id,
            runner=Mock(
                return_value=(
                    make_market_result()
                )
            ),
        )

    fail_mock.assert_called_once()

    assert (
        fail_mock.call_args.kwargs[
            "error_code"
        ]
        == "INVALID_MARKET_RESEARCH_RESULT"
    )

    assert len(
        session_factory.sessions
    ) == 3

    assert (
        session_factory
        .sessions[0]
        .commit_count
        == 1
    )

    assert (
        session_factory
        .sessions[1]
        .commit_count
        == 0
    )

    assert (
        session_factory
        .sessions[2]
        .commit_count
        == 1
    )


def test_executor_rejects_non_market_stage(
    monkeypatch,
):
    claim = make_claim(
        stage=(
            AnalysisStage
            .COMPETITOR_INTELLIGENCE
        )
    )

    monkeypatch.setattr(
        executor,
        "claim_research_stage",
        Mock(return_value=claim),
    )

    runner = Mock()

    session_factory = (
        FakeSessionFactory()
    )

    with pytest.raises(
        MarketResearchExecutionError
    ):
        executor.execute_market_research_stage(
            session_factory=session_factory,
            stage_run_id=claim.stage_run_id,
            runner=runner,
        )

    runner.assert_not_called()

    assert len(
        session_factory.sessions
    ) == 1

    assert (
        session_factory
        .sessions[0]
        .commit_count
        == 0
    )