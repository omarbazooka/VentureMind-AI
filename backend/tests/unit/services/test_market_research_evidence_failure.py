from unittest.mock import Mock
from uuid import uuid4

import pytest

import app.services.market_research_executor as executor

from app.research.market_evidence import (
    MarketEvidenceVerificationError,
)
from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisStage,
)
from app.schemas.intake import (
    ProfileReadinessStatus,
)
from app.schemas.research import (
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
        self.sessions: list[FakeSession] = []

    def __call__(self) -> FakeSession:
        session = FakeSession()
        self.sessions.append(session)
        return session


def make_claim() -> ResearchStageClaim:
    return ResearchStageClaim(
        stage_run_id=uuid4(),
        analysis_run_id=uuid4(),
        stage=AnalysisStage.MARKET_RESEARCH,
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


def test_evidence_failure_marks_stage_failed_without_persistence(
    monkeypatch,
):
    claim = make_claim()

    monkeypatch.setattr(
        executor,
        "claim_research_stage",
        Mock(return_value=claim),
    )

    complete_mock = Mock()
    fail_mock = Mock()

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
        side_effect=(
            MarketEvidenceVerificationError(
                "hallucinated source ID"
            )
        )
    )

    session_factory = FakeSessionFactory()

    with pytest.raises(
        MarketResearchExecutionError,
        match="evidence verification failed",
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
        == "INVALID_MARKET_RESEARCH_EVIDENCE"
    )

    assert len(session_factory.sessions) == 2
    assert session_factory.sessions[0].commit_count == 1
    assert session_factory.sessions[1].commit_count == 1
