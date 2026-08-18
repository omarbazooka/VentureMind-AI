from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ValidationError,
)
from sqlalchemy import select
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
    AnalysisProfileSnapshot,
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.research import (
    CompetitorAnalysis,
    CustomerAnalysis,
    MarketAnalysis,
    ResearchStageClaim,
)


RESEARCH_RESULT_SCHEMAS = {
    AnalysisStage.MARKET_RESEARCH: (
        MarketAnalysis
    ),
    AnalysisStage.COMPETITOR_INTELLIGENCE: (
        CompetitorAnalysis
    ),
    AnalysisStage.CUSTOMER_INTELLIGENCE: (
        CustomerAnalysis
    ),
}


class ResearchStageError(RuntimeError):
    pass


class ResearchStageNotFoundError(
    ResearchStageError
):
    pass


class ResearchStageRunNotFoundError(
    ResearchStageError
):
    pass


class ResearchStageStateError(
    ResearchStageError
):
    pass


class ResearchStageResultValidationError(
    ResearchStageError
):
    pass


def _normalize_research_stage(
    stage: str,
) -> AnalysisStage:
    try:
        normalized_stage = AnalysisStage(
            stage
        )
    except ValueError as exc:
        raise ResearchStageStateError(
            f"Unknown analysis stage: {stage}"
        ) from exc

    if (
        normalized_stage
        not in RESEARCH_RESULT_SCHEMAS
    ):
        raise ResearchStageStateError(
            "Stage is not a supported "
            "research stage"
        )

    return normalized_stage


def _load_stage_run_for_update(
    *,
    db: Session,
    stage_run_id: UUID,
) -> AnalysisStageRun:
    statement = (
        select(AnalysisStageRun)
        .where(
            AnalysisStageRun.id
            == stage_run_id
        )
        .with_for_update()
    )

    stage_run = db.scalar(
        statement
    )

    if stage_run is None:
        raise ResearchStageNotFoundError(
            "Research stage run not found"
        )

    return stage_run


def _load_analysis_run(
    *,
    db: Session,
    analysis_run_id: UUID,
) -> AnalysisRun:
    analysis_run = db.get(
        AnalysisRun,
        analysis_run_id,
    )

    if analysis_run is None:
        raise ResearchStageRunNotFoundError(
            "Parent analysis run not found"
        )

    return analysis_run


def claim_research_stage(
    *,
    db: Session,
    stage_run_id: UUID,
) -> ResearchStageClaim:
    stage_run = (
        _load_stage_run_for_update(
            db=db,
            stage_run_id=stage_run_id,
        )
    )

    stage = _normalize_research_stage(
        stage_run.stage
    )

    if (
        stage_run.status
        != AnalysisStageStatus.PENDING.value
    ):
        raise ResearchStageStateError(
            "Only a PENDING research stage "
            "can be claimed"
        )

    analysis_run = _load_analysis_run(
        db=db,
        analysis_run_id=(
            stage_run.analysis_run_id
        ),
    )

    if (
        analysis_run.status
        != AnalysisRunStatus.RUNNING.value
    ):
        raise ResearchStageStateError(
            "Research stage cannot start "
            "unless its AnalysisRun is RUNNING"
        )

    try:
        snapshot = (
            AnalysisProfileSnapshot
            .model_validate(
                analysis_run.profile_snapshot
            )
        )
    except ValidationError as exc:
        raise ResearchStageStateError(
            "Parent analysis run contains "
            "an invalid profile snapshot"
        ) from exc

    stage_run.status = (
        AnalysisStageStatus.RUNNING.value
    )

    if stage_run.started_at is None:
        stage_run.started_at = (
            datetime.now(timezone.utc)
        )

    stage_run.error_code = None
    stage_run.error_message = None

    db.flush()

    return ResearchStageClaim(
        stage_run_id=stage_run.id,
        analysis_run_id=(
            stage_run.analysis_run_id
        ),
        stage=stage,
        attempt=stage_run.attempt,
        profile_snapshot=snapshot,
    )


def _get_existing_result(
    *,
    db: Session,
    stage_run_id: UUID,
) -> AnalysisResult | None:
    statement = (
        select(AnalysisResult)
        .where(
            AnalysisResult.stage_run_id
            == stage_run_id
        )
    )

    return db.scalar(
        statement
    )


def _validate_research_result(
    *,
    stage: AnalysisStage,
    result_data: (
        dict[str, Any]
        | BaseModel
    ),
) -> BaseModel:
    schema = RESEARCH_RESULT_SCHEMAS[
        stage
    ]

    if isinstance(
        result_data,
        BaseModel,
    ):
        payload = result_data.model_dump(
            mode="json"
        )
    else:
        payload = result_data

    try:
        return schema.model_validate(
            payload
        )
    except ValidationError as exc:
        raise (
            ResearchStageResultValidationError(
                "Research stage returned "
                "an invalid structured result"
            )
        ) from exc


def complete_research_stage(
    *,
    db: Session,
    stage_run_id: UUID,
    result_data: (
        dict[str, Any]
        | BaseModel
    ),
) -> AnalysisResult:
    stage_run = (
        _load_stage_run_for_update(
            db=db,
            stage_run_id=stage_run_id,
        )
    )

    stage = _normalize_research_stage(
        stage_run.stage
    )

    existing_result = (
        _get_existing_result(
            db=db,
            stage_run_id=stage_run.id,
        )
    )

    if (
        stage_run.status
        == AnalysisStageStatus
        .COMPLETED
        .value
    ):
        if existing_result is None:
            raise ResearchStageStateError(
                "Completed stage has no "
                "persisted result"
            )

        return existing_result

    if (
        stage_run.status
        != AnalysisStageStatus.RUNNING.value
    ):
        raise ResearchStageStateError(
            "Only a RUNNING research stage "
            "can be completed"
        )

    if existing_result is not None:
        raise ResearchStageStateError(
            "Research stage already has "
            "a persisted result"
        )

    validated_result = (
        _validate_research_result(
            stage=stage,
            result_data=result_data,
        )
    )

    analysis_result = AnalysisResult(
        analysis_run_id=(
            stage_run.analysis_run_id
        ),
        stage_run_id=stage_run.id,
        stage=stage_run.stage,
        result_data=(
            validated_result.model_dump(
                mode="json"
            )
        ),
    )

    db.add(
        analysis_result
    )

    stage_run.status = (
        AnalysisStageStatus
        .COMPLETED
        .value
    )

    stage_run.completed_at = (
        datetime.now(timezone.utc)
    )

    stage_run.error_code = None
    stage_run.error_message = None

    db.flush()

    return analysis_result


def fail_research_stage(
    *,
    db: Session,
    stage_run_id: UUID,
    error_code: str,
    error_message: str,
) -> AnalysisStageRun:
    stage_run = (
        _load_stage_run_for_update(
            db=db,
            stage_run_id=stage_run_id,
        )
    )

    _normalize_research_stage(
        stage_run.stage
    )

    if (
        stage_run.status
        == AnalysisStageStatus.FAILED.value
    ):
        return stage_run

    if (
        stage_run.status
        != AnalysisStageStatus.RUNNING.value
    ):
        raise ResearchStageStateError(
            "Only a RUNNING research stage "
            "can fail"
        )

    cleaned_code = error_code.strip()
    cleaned_message = (
        error_message.strip()
    )

    if not cleaned_code:
        raise ValueError(
            "error_code cannot be empty"
        )

    if len(cleaned_code) > 100:
        raise ValueError(
            "error_code cannot exceed "
            "100 characters"
        )

    if not cleaned_message:
        raise ValueError(
            "error_message cannot be empty"
        )

    stage_run.status = (
        AnalysisStageStatus.FAILED.value
    )

    stage_run.error_code = cleaned_code
    stage_run.error_message = (
        cleaned_message
    )

    stage_run.completed_at = (
        datetime.now(timezone.utc)
    )

    db.flush()

    return stage_run