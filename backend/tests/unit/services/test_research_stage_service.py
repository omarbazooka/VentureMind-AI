from unittest.mock import Mock
from uuid import uuid4

import pytest
from pydantic import ValidationError
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
    ResearchStageClaim,
)
from app.services.research_stage import (
    ResearchStageResultValidationError,
    ResearchStageStateError,
    claim_research_stage,
    complete_research_stage,
    fail_research_stage,
)


def make_ready_snapshot() -> dict:
    return {
        "readiness": "READY_FOR_ANALYSIS",
        "profile_data": {
            "idea_description": (
                "Gym management SaaS"
            ),
            "target_customers": [
                "Independent gym owners"
            ],
            "target_country": "Egypt",
        },
        "profile_metadata": {
            "idea_description": {
                "provenance": "USER"
            },
            "target_customers": {
                "provenance": "USER"
            },
            "target_country": {
                "provenance": "USER"
            },
        },
        "unknown_fields": [],
    }


def make_stage_run(
    *,
    status: str = "PENDING",
    stage: str = "MARKET_RESEARCH",
) -> AnalysisStageRun:
    return AnalysisStageRun(
        id=uuid4(),
        analysis_run_id=uuid4(),
        stage=stage,
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


def test_claim_moves_pending_stage_to_running():
    stage_run = make_stage_run()

    analysis_run = make_analysis_run(
        stage_run
    )

    db = Mock(spec=Session)
    db.scalar.return_value = stage_run
    db.get.return_value = analysis_run

    claim = claim_research_stage(
        db=db,
        stage_run_id=stage_run.id,
    )

    assert isinstance(
        claim,
        ResearchStageClaim,
    )

    assert (
        stage_run.status
        == AnalysisStageStatus
        .RUNNING
        .value
    )

    assert stage_run.started_at is not None

    assert (
        claim.stage
        == AnalysisStage.MARKET_RESEARCH
    )

    assert (
        claim.profile_snapshot
        .profile_data["target_country"]
        == "Egypt"
    )

    db.flush.assert_called_once_with()


def test_claim_rejects_non_running_parent():
    stage_run = make_stage_run()

    analysis_run = make_analysis_run(
        stage_run,
        status=(
            AnalysisRunStatus
            .CANCELLED.value
        ),
    )

    db = Mock(spec=Session)
    db.scalar.return_value = stage_run
    db.get.return_value = analysis_run

    with pytest.raises(
        ResearchStageStateError
    ):
        claim_research_stage(
            db=db,
            stage_run_id=stage_run.id,
        )

    assert (
        stage_run.status
        == AnalysisStageStatus
        .PENDING.value
    )


def test_complete_persists_valid_result():
    stage_run = make_stage_run(
        status=(
            AnalysisStageStatus
            .RUNNING.value
        )
    )

    db = Mock(spec=Session)

    db.scalar.side_effect = [
        stage_run,
        None,
    ]

    result = complete_research_stage(
        db=db,
        stage_run_id=stage_run.id,
        result_data={
            "summary": (
                "Reliable evidence "
                "was insufficient."
            ),
            "findings": [],
            "evidence_sources": [],
            "evidence_quality": (
                "INSUFFICIENT"
            ),
            "limitations": [
                "No reliable market "
                "sources were available."
            ],
        },
    )

    assert isinstance(
        result,
        AnalysisResult,
    )

    assert (
        result.analysis_run_id
        == stage_run.analysis_run_id
    )

    assert (
        result.stage_run_id
        == stage_run.id
    )

    assert (
        result.stage
        == AnalysisStage
        .MARKET_RESEARCH.value
    )

    assert (
        stage_run.status
        == AnalysisStageStatus
        .COMPLETED.value
    )

    assert (
        stage_run.completed_at
        is not None
    )

    db.add.assert_called_once_with(
        result
    )


def test_complete_rejects_invalid_result():
    stage_run = make_stage_run(
        status=(
            AnalysisStageStatus
            .RUNNING.value
        )
    )

    db = Mock(spec=Session)

    db.scalar.side_effect = [
        stage_run,
        None,
    ]

    with pytest.raises(
        ResearchStageResultValidationError
    ):
        complete_research_stage(
            db=db,
            stage_run_id=stage_run.id,
            result_data={
                "summary": "Bad result",
                "findings": [],
                "evidence_sources": [],
                "evidence_quality": "STRONG",
                "limitations": [],
            },
        )

    assert (
        stage_run.status
        == AnalysisStageStatus
        .RUNNING.value
    )

    db.add.assert_not_called()


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
            "summary": "Existing"
        },
    )

    db = Mock(spec=Session)

    db.scalar.side_effect = [
        stage_run,
        existing_result,
    ]

    result = complete_research_stage(
        db=db,
        stage_run_id=stage_run.id,
        result_data={},
    )

    assert result is existing_result

    db.add.assert_not_called()


def test_fail_records_error():
    stage_run = make_stage_run(
        status=(
            AnalysisStageStatus
            .RUNNING.value
        )
    )

    db = Mock(spec=Session)
    db.scalar.return_value = stage_run

    result = fail_research_stage(
        db=db,
        stage_run_id=stage_run.id,
        error_code="WEB_TIMEOUT",
        error_message=(
            "Research provider timed out."
        ),
    )

    assert result is stage_run

    assert (
        stage_run.status
        == AnalysisStageStatus
        .FAILED.value
    )

    assert (
        stage_run.error_code
        == "WEB_TIMEOUT"
    )

    assert (
        stage_run.error_message
        == "Research provider timed out."
    )

    assert (
        stage_run.completed_at
        is not None
    )

    db.flush.assert_called_once_with()