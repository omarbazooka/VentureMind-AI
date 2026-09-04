from unittest.mock import Mock
from uuid import uuid4

import pytest

import app.services.business_strategy_executor as executor

from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.intake import (
    ProfileReadinessStatus,
)
from app.schemas.research import (
    ResearchEvidenceGateResult,
    ResearchEvidenceQuality,
    ResearchGateDecision,
    ResearchStageGateAssessment,
)
from app.schemas.strategy import (
    BusinessStrategyAnalysis,
    StrategyStageClaim,
)
from app.services.business_strategy_executor import (
    BusinessStrategyExecutionError,
)
from app.services.strategy_grounding import (
    StrategyGroundingError,
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


def make_claim() -> StrategyStageClaim:
    research_stages = [
        AnalysisStage.MARKET_RESEARCH,
        AnalysisStage.COMPETITOR_INTELLIGENCE,
        AnalysisStage.CUSTOMER_INTELLIGENCE,
    ]

    gate = ResearchEvidenceGateResult(
        decision=(
            ResearchGateDecision.INSUFFICIENT
        ),
        can_proceed=True,
        assessments=[
            ResearchStageGateAssessment(
                stage=stage,
                attempt=1,
                stage_status=(
                    AnalysisStageStatus.COMPLETED
                ),
                evidence_quality=(
                    ResearchEvidenceQuality
                    .INSUFFICIENT
                ),
            )
            for stage in research_stages
        ],
        insufficient_stages=(
            research_stages
        ),
    )

    return StrategyStageClaim(
        stage_run_id=uuid4(),
        analysis_run_id=uuid4(),
        stage=(
            AnalysisStage.BUSINESS_STRATEGY
        ),
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
                    "target_country": "Egypt",
                },
            )
        ),
        research_gate=gate,
    )


def make_strategy_result(
) -> BusinessStrategyAnalysis:
    return BusinessStrategyAnalysis(
        executive_summary=(
            "Available evidence is too limited "
            "for strong strategic conclusions."
        ),
        limitations=[
            "Research evidence remains "
            "insufficient."
        ],
        finance_questions=[
            "What selling price should "
            "be evaluated?"
        ],
    )


def test_executor_completes_strategy_stage(
    monkeypatch,
):
    claim = make_claim()

    strategy_result = (
        make_strategy_result()
    )

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
        "claim_strategy_stage",
        claim_mock,
    )

    monkeypatch.setattr(
        executor,
        "complete_strategy_stage",
        complete_mock,
    )

    monkeypatch.setattr(
        executor,
        "fail_strategy_stage",
        fail_mock,
    )

    runner = Mock(
        return_value=strategy_result
    )

    session_factory = (
        FakeSessionFactory()
    )

    result = (
        executor
        .execute_business_strategy_stage(
            session_factory=session_factory,
            stage_run_id=(
                claim.stage_run_id
            ),
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


def test_executor_marks_runner_failure(
    monkeypatch,
):
    claim = make_claim()

    monkeypatch.setattr(
        executor,
        "claim_strategy_stage",
        Mock(return_value=claim),
    )

    complete_mock = Mock()

    monkeypatch.setattr(
        executor,
        "complete_strategy_stage",
        complete_mock,
    )

    fail_mock = Mock()

    monkeypatch.setattr(
        executor,
        "fail_strategy_stage",
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
        BusinessStrategyExecutionError
    ):
        (
            executor
            .execute_business_strategy_stage(
                session_factory=(
                    session_factory
                ),
                stage_run_id=(
                    claim.stage_run_id
                ),
                runner=runner,
            )
        )

    complete_mock.assert_not_called()

    fail_mock.assert_called_once()

    assert (
        fail_mock.call_args.kwargs[
            "error_code"
        ]
        == (
            "BUSINESS_STRATEGY_"
            "EXECUTION_ERROR"
        )
    )

    assert len(
        session_factory.sessions
    ) == 2


def test_executor_marks_grounding_failure(
    monkeypatch,
):
    claim = make_claim()

    monkeypatch.setattr(
        executor,
        "claim_strategy_stage",
        Mock(return_value=claim),
    )

    monkeypatch.setattr(
        executor,
        "complete_strategy_stage",
        Mock(),
    )

    fail_mock = Mock()

    monkeypatch.setattr(
        executor,
        "fail_strategy_stage",
        fail_mock,
    )

    runner = Mock(
        side_effect=(
            StrategyGroundingError(
                "invented evidence"
            )
        )
    )

    session_factory = (
        FakeSessionFactory()
    )

    with pytest.raises(
        BusinessStrategyExecutionError
    ):
        (
            executor
            .execute_business_strategy_stage(
                session_factory=(
                    session_factory
                ),
                stage_run_id=(
                    claim.stage_run_id
                ),
                runner=runner,
            )
        )

    assert (
        fail_mock.call_args.kwargs[
            "error_code"
        ]
        == (
            "INVALID_BUSINESS_"
            "STRATEGY_GROUNDING"
        )
    )


def test_executor_marks_invalid_result_failed(
    monkeypatch,
):
    claim = make_claim()

    monkeypatch.setattr(
        executor,
        "claim_strategy_stage",
        Mock(return_value=claim),
    )

    monkeypatch.setattr(
        executor,
        "complete_strategy_stage",
        Mock(
            side_effect=(
                executor
                .StrategyStageResultValidationError(
                    "invalid result"
                )
            )
        ),
    )

    fail_mock = Mock()

    monkeypatch.setattr(
        executor,
        "fail_strategy_stage",
        fail_mock,
    )

    session_factory = (
        FakeSessionFactory()
    )

    with pytest.raises(
        BusinessStrategyExecutionError
    ):
        (
            executor
            .execute_business_strategy_stage(
                session_factory=(
                    session_factory
                ),
                stage_run_id=(
                    claim.stage_run_id
                ),
                runner=Mock(
                    return_value=(
                        make_strategy_result()
                    )
                ),
            )
        )

    fail_mock.assert_called_once()

    assert (
        fail_mock.call_args.kwargs[
            "error_code"
        ]
        == (
            "INVALID_BUSINESS_"
            "STRATEGY_RESULT"
        )
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