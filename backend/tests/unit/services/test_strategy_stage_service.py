from unittest.mock import (
    Mock,
)
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.analysis_result import (
    AnalysisResult,
)
from app.models.analysis_run import (
    AnalysisRun,
)
from app.models.analysis_stage_run import (
    AnalysisStageRun,
)
from app.schemas.analysis import (
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.research import (
    ResearchEvidenceGateResult,
    ResearchEvidenceQuality,
    ResearchGateDecision,
    ResearchStageGateAssessment,
)
from app.schemas.strategy import (
    StrategyStageClaim,
)
from app.services.research_join import (
    ResearchJoinEvaluation,
)
from app.services.strategy_stage import (
    StrategyStageResultValidationError,
    StrategyStageStateError,
    claim_strategy_stage,
    complete_strategy_stage,
    fail_strategy_stage,
)


def make_ready_snapshot() -> dict:
    return {
        "readiness": (
            "READY_FOR_ANALYSIS"
        ),
        "profile_data": {
            "idea_description": (
                "Gym management SaaS"
            ),
            "target_customers": [
                "Independent gym owners"
            ],
            "target_country": "Egypt",
        },
        "profile_metadata": {},
        "unknown_fields": [],
    }


def make_stage_run(
    *,
    status: str = "PENDING",
) -> AnalysisStageRun:
    return AnalysisStageRun(
        id=uuid4(),
        analysis_run_id=uuid4(),
        stage=(
            AnalysisStage
            .BUSINESS_STRATEGY
            .value
        ),
        attempt=1,
        status=status,
    )


def make_analysis_run(
    stage_run: AnalysisStageRun,
    *,
    status: str = "RUNNING",
) -> AnalysisRun:
    return AnalysisRun(
        id=stage_run.analysis_run_id,
        idea_id=uuid4(),
        profile_id=uuid4(),
        profile_version=2,
        profile_snapshot=(
            make_ready_snapshot()
        ),
        status=status,
    )


def make_gate(
    *,
    can_proceed: bool = True,
) -> ResearchEvidenceGateResult:
    stages = [
        AnalysisStage.MARKET_RESEARCH,
        AnalysisStage
        .COMPETITOR_INTELLIGENCE,
        AnalysisStage
        .CUSTOMER_INTELLIGENCE,
    ]

    if not can_proceed:
        return ResearchEvidenceGateResult(
            decision=(
                ResearchGateDecision.RETRY
            ),
            can_proceed=False,
            assessments=[
                ResearchStageGateAssessment(
                    stage=stage,
                    attempt=1,
                    stage_status=(
                        AnalysisStageStatus
                        .COMPLETED
                    ),
                    evidence_quality=(
                        ResearchEvidenceQuality
                        .WEAK
                    ),
                    retry_eligible=True,
                )
                for stage in stages
            ],
            retry_stages=stages,
        )

    return ResearchEvidenceGateResult(
        decision=(
            ResearchGateDecision
            .INSUFFICIENT
        ),
        can_proceed=True,
        assessments=[
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
            )
            for stage in stages
        ],
        insufficient_stages=stages,
    )


def make_evaluation(
    analysis_run_id,
    *,
    can_proceed: bool = True,
) -> ResearchJoinEvaluation:
    return ResearchJoinEvaluation(
        analysis_run_id=(
            analysis_run_id
        ),
        gate=make_gate(
            can_proceed=can_proceed,
        ),
        results={},
        latest_stage_run_ids={},
        result_stage_run_ids={},
    )


def test_claim_moves_strategy_to_running(
    monkeypatch,
):
    stage_run = make_stage_run()

    analysis_run = make_analysis_run(
        stage_run
    )

    db = Mock(
        spec=Session
    )

    db.scalar.return_value = (
        stage_run
    )

    db.get.return_value = (
        analysis_run
    )

    monkeypatch.setattr(
        (
            "app.services.strategy_stage."
            "inspect_research_join"
        ),
        Mock(
            return_value=(
                make_evaluation(
                    analysis_run.id
                )
            )
        ),
    )

    claim = claim_strategy_stage(
        db=db,
        stage_run_id=stage_run.id,
    )

    assert isinstance(
        claim,
        StrategyStageClaim,
    )

    assert (
        claim.stage
        == AnalysisStage
        .BUSINESS_STRATEGY
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

    assert (
        claim.profile_snapshot
        .profile_data[
            "target_country"
        ]
        == "Egypt"
    )

    db.flush.assert_called_once_with()


def test_claim_rejects_blocked_gate(
    monkeypatch,
):
    stage_run = make_stage_run()

    analysis_run = make_analysis_run(
        stage_run
    )

    db = Mock(
        spec=Session
    )

    db.scalar.return_value = (
        stage_run
    )

    db.get.return_value = (
        analysis_run
    )

    monkeypatch.setattr(
        (
            "app.services.strategy_stage."
            "inspect_research_join"
        ),
        Mock(
            return_value=(
                make_evaluation(
                    analysis_run.id,
                    can_proceed=False,
                )
            )
        ),
    )

    with pytest.raises(
        StrategyStageStateError
    ):
        claim_strategy_stage(
            db=db,
            stage_run_id=stage_run.id,
        )

    assert (
        stage_run.status
        == AnalysisStageStatus
        .PENDING
        .value
    )


def test_claim_rejects_non_running_parent(
    monkeypatch,
):
    stage_run = make_stage_run()

    analysis_run = make_analysis_run(
        stage_run,
        status=(
            AnalysisRunStatus
            .CANCELLED.value
        ),
    )

    db = Mock(
        spec=Session
    )

    db.scalar.return_value = (
        stage_run
    )

    db.get.return_value = (
        analysis_run
    )

    with pytest.raises(
        StrategyStageStateError
    ):
        claim_strategy_stage(
            db=db,
            stage_run_id=stage_run.id,
        )


def test_complete_persists_grounded_strategy(
    monkeypatch,
):
    stage_run = make_stage_run(
        status=(
            AnalysisStageStatus
            .RUNNING.value
        )
    )

    analysis_run = make_analysis_run(
        stage_run
    )

    db = Mock(
        spec=Session
    )

    db.scalar.side_effect = [
        stage_run,
        None,
    ]

    db.get.return_value = (
        analysis_run
    )

    monkeypatch.setattr(
        (
            "app.services.strategy_stage."
            "inspect_research_join"
        ),
        Mock(
            return_value=(
                make_evaluation(
                    analysis_run.id
                )
            )
        ),
    )

    result = complete_strategy_stage(
        db=db,
        stage_run_id=stage_run.id,
        result_data={
            "executive_summary": (
                "Evidence remains limited."
            ),
            "limitations": [
                (
                    "Market, competitor, and "
                    "customer evidence remain "
                    "insufficient."
                )
            ],
        },
    )

    assert isinstance(
        result,
        AnalysisResult,
    )

    assert (
        result.stage
        == AnalysisStage
        .BUSINESS_STRATEGY
        .value
    )

    assert (
        stage_run.status
        == AnalysisStageStatus
        .COMPLETED
        .value
    )

    assert (
        stage_run.completed_at
        is not None
    )

    db.add.assert_called_once_with(
        result
    )


def test_complete_rejects_ungrounded_result(
    monkeypatch,
):
    stage_run = make_stage_run(
        status=(
            AnalysisStageStatus
            .RUNNING.value
        )
    )

    analysis_run = make_analysis_run(
        stage_run
    )

    db = Mock(
        spec=Session
    )

    db.scalar.side_effect = [
        stage_run,
        None,
    ]

    db.get.return_value = (
        analysis_run
    )

    monkeypatch.setattr(
        (
            "app.services.strategy_stage."
            "inspect_research_join"
        ),
        Mock(
            return_value=(
                make_evaluation(
                    analysis_run.id
                )
            )
        ),
    )

    with pytest.raises(
        StrategyStageResultValidationError
    ):
        complete_strategy_stage(
            db=db,
            stage_run_id=stage_run.id,
            result_data={
                "executive_summary": (
                    "Strategy summary."
                ),
                "positioning": [
                    {
                        "statement": (
                            "The venture has "
                            "validated revenue."
                        ),
                        "claim_kind": (
                            "PROFILE_FACT"
                        ),
                        "confidence": 1.0,
                        "profile_fields": [
                            "invented_field"
                        ],
                    }
                ],
                "limitations": [
                    "Research is limited."
                ],
            },
        )

    db.add.assert_not_called()

    assert (
        stage_run.status
        == AnalysisStageStatus
        .RUNNING.value
    )


def test_complete_is_idempotent():
    stage_run = make_stage_run(
        status=(
            AnalysisStageStatus
            .COMPLETED.value
        )
    )

    existing_result = AnalysisResult(
        id=uuid4(),
        analysis_run_id=(
            stage_run.analysis_run_id
        ),
        stage_run_id=stage_run.id,
        stage=stage_run.stage,
        result_data={
            "executive_summary": (
                "Existing strategy."
            )
        },
    )

    db = Mock(
        spec=Session
    )

    db.scalar.side_effect = [
        stage_run,
        existing_result,
    ]

    result = complete_strategy_stage(
        db=db,
        stage_run_id=stage_run.id,
        result_data={},
    )

    assert (
        result is existing_result
    )

    db.add.assert_not_called()


def test_fail_records_strategy_error():
    stage_run = make_stage_run(
        status=(
            AnalysisStageStatus
            .RUNNING.value
        )
    )

    db = Mock(
        spec=Session
    )

    db.scalar.return_value = (
        stage_run
    )

    result = fail_strategy_stage(
        db=db,
        stage_run_id=stage_run.id,
        error_code=(
            "STRATEGY_LLM_ERROR"
        ),
        error_message=(
            "Strategy generation failed."
        ),
    )

    assert result is stage_run

    assert (
        stage_run.status
        == AnalysisStageStatus
        .FAILED
        .value
    )

    assert (
        stage_run.error_code
        == "STRATEGY_LLM_ERROR"
    )

    assert (
        stage_run.completed_at
        is not None
    )

    db.flush.assert_called_once_with()