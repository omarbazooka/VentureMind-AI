from types import SimpleNamespace
from unittest.mock import (
    Mock,
    patch,
)
from uuid import uuid4

import pytest

from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisRunStatus,
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
    ResearchGateIssueCode,
    ResearchStageGateAssessment,
)
from app.schemas.strategy import (
    BusinessStrategyAnalysis,
)
from app.services.finance_stage import (
    FinanceStageDependencyError,
    FinanceStageStateError,
    claim_finance_stage,
)


def make_gate(
) -> ResearchEvidenceGateResult:
    research_stages = (
        AnalysisStage.MARKET_RESEARCH,
        AnalysisStage
        .COMPETITOR_INTELLIGENCE,
        AnalysisStage
        .CUSTOMER_INTELLIGENCE,
    )

    assessments = [
        ResearchStageGateAssessment(
            stage=stage,
            attempt=1,
            stage_status=(
                AnalysisStageStatus
                .COMPLETED
            ),
            evidence_quality=(
                ResearchEvidenceQuality
                .INSUFFICIENT
            ),
            limitations=[
                "Evidence remains limited."
            ],
            retry_eligible=False,
            issue_codes=[
                ResearchGateIssueCode
                .INSUFFICIENT_EVIDENCE
            ],
        )
        for stage in research_stages
    ]

    return ResearchEvidenceGateResult(
        decision=(
            ResearchGateDecision
            .INSUFFICIENT
        ),
        can_proceed=True,
        assessments=assessments,
        retry_stages=[],
        insufficient_stages=[
            *research_stages
        ],
    )


def make_snapshot(
) -> AnalysisProfileSnapshot:
    return AnalysisProfileSnapshot(
        readiness=(
            ProfileReadinessStatus
            .READY_FOR_ANALYSIS
        ),
        profile_data={
            "idea_description": (
                "Gym management SaaS."
            ),
            "target_country": "Egypt",
        },
        profile_metadata={},
        unknown_fields=[],
    )


def make_strategy(
) -> BusinessStrategyAnalysis:
    return BusinessStrategyAnalysis(
        executive_summary=(
            "Proceed to bounded "
            "financial analysis."
        ),
        finance_questions=[
            (
                "What selling price "
                "should be modeled?"
            )
        ],
    )


def make_db_setup():
    analysis_run_id = uuid4()
    stage_run_id = uuid4()

    stage_run = SimpleNamespace(
        id=stage_run_id,
        analysis_run_id=analysis_run_id,
        stage=(
            AnalysisStage.FINANCE.value
        ),
        attempt=1,
        status=(
            AnalysisStageStatus
            .PENDING
            .value
        ),
        started_at=None,
        error_code=None,
        error_message=None,
    )

    analysis_run = SimpleNamespace(
        id=analysis_run_id,
        status=(
            AnalysisRunStatus
            .RUNNING
            .value
        ),
        profile_snapshot=(
            make_snapshot()
            .model_dump(
                mode="json"
            )
        ),
    )

    strategy_result = SimpleNamespace(
        result_data=(
            make_strategy()
            .model_dump(
                mode="json"
            )
        ),
    )

    db = Mock()

    db.scalar.side_effect = [
        stage_run,
        strategy_result,
    ]

    db.get.return_value = (
        analysis_run
    )

    return (
        db,
        stage_run,
        analysis_run,
    )

def test_claim_finance_stage_builds_authoritative_context():
    (
        db,
        stage_run,
        analysis_run,
    ) = make_db_setup()

    evaluation = SimpleNamespace(
        gate=make_gate(),
        results={},
    )

    with patch(
        (
            "app.services.finance_stage"
            ".inspect_research_join"
        ),
        return_value=evaluation,
    ):
        claim = claim_finance_stage(
            db=db,
            stage_run_id=stage_run.id,
        )

    assert (
        claim.stage
        == AnalysisStage.FINANCE
    )

    assert (
        claim.analysis_run_id
        == analysis_run.id
    )

    assert (
        claim
        .assumption_context
        .business_strategy
        .executive_summary
        == (
            "Proceed to bounded "
            "financial analysis."
        )
    )

    assert (
        stage_run.status
        == AnalysisStageStatus
        .RUNNING
        .value
    )

    assert (
        stage_run.started_at
        is not None
    )

    db.flush.assert_called_once()

def test_claim_finance_stage_requires_running_analysis():
    (
        db,
        stage_run,
        analysis_run,
    ) = make_db_setup()

    analysis_run.status = (
        AnalysisRunStatus
        .PAUSED_FOR_USER
        .value
    )

    with pytest.raises(
        FinanceStageStateError
    ):
        claim_finance_stage(
            db=db,
            stage_run_id=stage_run.id,
        )

def test_claim_finance_stage_requires_completed_strategy():
    (
        db,
        stage_run,
        _,
    ) = make_db_setup()

    db.scalar.side_effect = [
        stage_run,
        None,
    ]

    with pytest.raises(
        FinanceStageDependencyError
    ):
        claim_finance_stage(
            db=db,
            stage_run_id=stage_run.id,
        )

    assert (
        stage_run.status
        == AnalysisStageStatus
        .PENDING
        .value
    )