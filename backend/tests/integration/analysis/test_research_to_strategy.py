from collections.abc import Callable
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import engine
from app.flows.business_analysis_flow import (
    BusinessAnalysisFlow,
)
from app.models.analysis_result import (
    AnalysisResult,
)
from app.models.analysis_run import (
    AnalysisRun,
)
from app.models.analysis_stage_run import (
    AnalysisStageRun,
)
from app.models.idea import Idea
from app.models.idea_profile import (
    IdeaProfile,
)
from app.schemas.analysis import (
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.research import (
    ResearchEvidenceQuality,
)
from app.schemas.strategy import (
    BusinessStrategyAnalysis,
)
from app.services.business_strategy_executor import (
    execute_business_strategy_stage,
)


SessionFactory = Callable[
    [],
    Session,
]


@pytest.fixture
def integration_session_factory(
) -> SessionFactory:
    connection = engine.connect()
    transaction = connection.begin()

    def factory() -> Session:
        return Session(
            bind=connection,
            autoflush=False,
            expire_on_commit=False,
            join_transaction_mode=(
                "create_savepoint"
            ),
        )

    try:
        yield factory

    finally:
        transaction.rollback()
        connection.close()


def make_ready_snapshot() -> dict:
    return {
        "readiness": (
            "READY_FOR_ANALYSIS"
        ),
        "profile_data": {
            "idea_description": (
                "A SaaS platform for "
                "independent gyms."
            ),
            "target_customers": [
                "Independent gym owners"
            ],
            "target_country": "Egypt",
        },
        "profile_metadata": {},
        "unknown_fields": [],
    }


def make_insufficient_research_result(
    stage: AnalysisStage,
) -> dict:
    result = {
        "summary": (
            "Reliable evidence is currently "
            "insufficient for strong conclusions."
        ),
        "findings": [],
        "evidence_sources": [],
        "evidence_quality": (
            ResearchEvidenceQuality
            .INSUFFICIENT
            .value
        ),
        "limitations": [
            (
                "Reliable public evidence "
                "was insufficient."
            )
        ],
    }

    if (
        stage
        == AnalysisStage
        .COMPETITOR_INTELLIGENCE
    ):
        result["competitors"] = []

    return result


def seed_completed_research(
    *,
    session_factory: SessionFactory,
) -> AnalysisRun:
    idea_id = uuid4()
    profile_id = uuid4()
    run_id = uuid4()

    snapshot = make_ready_snapshot()

    with session_factory() as db:
        idea = Idea(
            id=idea_id,
            title="Gym SaaS",
            raw_initial_idea=(
                "Software for independent "
                "gym owners."
            ),
        )

        db.add(idea)
        db.flush()

        profile = IdeaProfile(
            id=profile_id,
            idea_id=idea_id,
            version=1,
            readiness=(
                "READY_FOR_ANALYSIS"
            ),
            profile_data=(
                snapshot["profile_data"]
            ),
            profile_metadata={},
            unknown_fields=[],
        )

        db.add(profile)
        db.flush()

        analysis_run = AnalysisRun(
            id=run_id,
            idea_id=idea_id,
            profile_id=profile_id,
            profile_version=1,
            profile_snapshot=snapshot,
            status=(
                AnalysisRunStatus
                .RUNNING
                .value
            ),
        )

        db.add(analysis_run)
        db.flush()

        research_stages = (
            AnalysisStage.MARKET_RESEARCH,
            AnalysisStage
            .COMPETITOR_INTELLIGENCE,
            AnalysisStage
            .CUSTOMER_INTELLIGENCE,
        )

        for stage in research_stages:
            stage_run = (
                AnalysisStageRun(
                    id=uuid4(),
                    analysis_run_id=run_id,
                    stage=stage.value,
                    attempt=1,
                    status=(
                        AnalysisStageStatus
                        .COMPLETED
                        .value
                    ),
                )
            )

            db.add(stage_run)
            db.flush()

            db.add(
                AnalysisResult(
                    id=uuid4(),
                    analysis_run_id=run_id,
                    stage_run_id=(
                        stage_run.id
                    ),
                    stage=stage.value,
                    result_data=(
                        make_insufficient_research_result(
                            stage
                        )
                    ),
                )
            )

        db.commit()

        return analysis_run


def test_research_gate_to_persisted_strategy(
    integration_session_factory,
):
    session_factory = (
        integration_session_factory
    )

    analysis_run = (
        seed_completed_research(
            session_factory=(
                session_factory
            )
        )
    )

    with session_factory() as db:
        step = (
            BusinessAnalysisFlow()
            .advance_research(
                db=db,
                run_id=analysis_run.id,
            )
        )

        db.commit()

    assert (
        step.evaluation
        .gate
        .can_proceed
        is True
    )

    assert (
        step.evaluation
        .gate
        .insufficient_stages
    )

    assert (
        step.scheduled_retries
        == []
    )

    assert (
        step.strategy_stage_run_id
        is not None
    )

    captured_claims = []

    def fake_strategy_runner(
        claim,
    ) -> BusinessStrategyAnalysis:
        captured_claims.append(
            claim
        )

        return BusinessStrategyAnalysis(
            executive_summary=(
                "The venture can proceed "
                "to bounded strategy work, "
                "but research confidence "
                "remains limited."
            ),
            limitations=[
                (
                    "Market, competitor, "
                    "and customer evidence "
                    "remain insufficient."
                )
            ],
            finance_questions=[
                (
                    "What selling price "
                    "should Finance evaluate?"
                )
            ],
        )

    persisted_result = (
        execute_business_strategy_stage(
            session_factory=session_factory,
            stage_run_id=(
                step.strategy_stage_run_id
            ),
            runner=(
                fake_strategy_runner
            ),
        )
    )

    assert (
        persisted_result.stage
        == (
            AnalysisStage
            .BUSINESS_STRATEGY
            .value
        )
    )

    assert len(
        captured_claims
    ) == 1

    strategy_claim = (
        captured_claims[0]
    )

    assert (
        strategy_claim.stage
        == AnalysisStage
        .BUSINESS_STRATEGY
    )

    assert (
        strategy_claim.analysis_run_id
        == analysis_run.id
    )

    assert (
        strategy_claim
        .research_gate
        .can_proceed
        is True
    )

    assert (
        strategy_claim.market_analysis
        is not None
    )

    assert (
        strategy_claim
        .competitor_analysis
        is not None
    )

    assert (
        strategy_claim.customer_analysis
        is not None
    )

    with session_factory() as db:
        strategy_stage = db.get(
            AnalysisStageRun,
            step.strategy_stage_run_id,
        )

        assert (
            strategy_stage
            is not None
        )

        assert (
            strategy_stage.status
            == (
                AnalysisStageStatus
                .COMPLETED
                .value
            )
        )

        assert (
            strategy_stage.started_at
            is not None
        )

        assert (
            strategy_stage.completed_at
            is not None
        )

        statement = (
            select(AnalysisResult)
            .where(
                AnalysisResult.stage_run_id
                == (
                    step
                    .strategy_stage_run_id
                )
            )
        )

        stored_result = db.scalar(
            statement
        )

        assert (
            stored_result
            is not None
        )

        assert (
            stored_result.stage
            == (
                AnalysisStage
                .BUSINESS_STRATEGY
                .value
            )
        )

        assert (
            stored_result.result_data[
                "executive_summary"
            ]
            == (
                "The venture can proceed "
                "to bounded strategy work, "
                "but research confidence "
                "remains limited."
            )
        )