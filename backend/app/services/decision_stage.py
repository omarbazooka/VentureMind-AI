from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.models.analysis_run import AnalysisRun
from app.models.analysis_stage_run import AnalysisStageRun
from app.schemas.analysis import (
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.decision import FinalDecisionAnalysis
from app.schemas.decision_runtime import DecisionStageClaim
from app.services.decision_context import (
    DecisionContextDependencyError,
    build_investment_committee_context,
)


class DecisionStageError(RuntimeError):
    pass


class DecisionStageNotFoundError(DecisionStageError):
    pass


class DecisionStageRunNotFoundError(DecisionStageError):
    pass


class DecisionStageStateError(DecisionStageError):
    pass


class DecisionStageDependencyError(DecisionStageError):
    pass


class DecisionStageResultValidationError(DecisionStageError):
    pass


def _normalize_decision_stage(stage: str) -> AnalysisStage:
    try:
        normalized = AnalysisStage(stage)
    except ValueError as exc:
        raise DecisionStageStateError(
            f"Unknown analysis stage: {stage}"
        ) from exc

    if normalized != AnalysisStage.INVESTMENT_COMMITTEE:
        raise DecisionStageStateError("Stage is not INVESTMENT_COMMITTEE")

    return normalized


def _load_stage_run_for_update(
    *,
    db: Session,
    stage_run_id: UUID,
) -> AnalysisStageRun:
    statement = (
        select(AnalysisStageRun)
        .where(AnalysisStageRun.id == stage_run_id)
        .with_for_update()
    )
    stage_run = db.scalar(statement)

    if stage_run is None:
        raise DecisionStageNotFoundError(
            "Decision stage run not found"
        )

    return stage_run


def _load_analysis_run(
    *,
    db: Session,
    analysis_run_id: UUID,
) -> AnalysisRun:
    analysis_run = db.get(AnalysisRun, analysis_run_id)
    if analysis_run is None:
        raise DecisionStageRunNotFoundError(
            "Parent analysis run not found"
        )

    if analysis_run.status != AnalysisRunStatus.RUNNING.value:
        raise DecisionStageStateError(
            "Investment Committee cannot run unless its AnalysisRun is RUNNING"
        )

    return analysis_run


def claim_decision_stage(
    *,
    db: Session,
    stage_run_id: UUID,
) -> DecisionStageClaim:
    stage_run = _load_stage_run_for_update(
        db=db,
        stage_run_id=stage_run_id,
    )
    _normalize_decision_stage(stage_run.stage)

    if stage_run.status != AnalysisStageStatus.PENDING.value:
        raise DecisionStageStateError(
            "Only a PENDING Investment Committee stage can be claimed"
        )

    analysis_run = _load_analysis_run(
        db=db,
        analysis_run_id=stage_run.analysis_run_id,
    )
    try:
        context = build_investment_committee_context(
            db=db,
            analysis_run_id=analysis_run.id,
        )
    except DecisionContextDependencyError as exc:
        raise DecisionStageDependencyError(
            "Investment Committee cannot build its authoritative upstream context"
        ) from exc

    claim = DecisionStageClaim(
        stage_run_id=stage_run.id,
        analysis_run_id=analysis_run.id,
        stage=AnalysisStage.INVESTMENT_COMMITTEE,
        attempt=stage_run.attempt,
        context=context,
    )

    stage_run.status = AnalysisStageStatus.RUNNING.value
    if stage_run.started_at is None:
        stage_run.started_at = datetime.now(timezone.utc)
    stage_run.error_code = None
    stage_run.error_message = None

    db.flush()
    return claim


def _get_existing_result(
    *,
    db: Session,
    stage_run_id: UUID,
) -> AnalysisResult | None:
    return db.scalar(
        select(AnalysisResult).where(
            AnalysisResult.stage_run_id == stage_run_id
        )
    )


def complete_decision_stage(
    *,
    db: Session,
    stage_run_id: UUID,
    result_data: dict[str, Any] | BaseModel,
) -> AnalysisResult:
    stage_run = _load_stage_run_for_update(
        db=db,
        stage_run_id=stage_run_id,
    )
    _normalize_decision_stage(stage_run.stage)

    existing_result = _get_existing_result(
        db=db,
        stage_run_id=stage_run.id,
    )

    if stage_run.status == AnalysisStageStatus.COMPLETED.value:
        if existing_result is None:
            raise DecisionStageStateError(
                "Completed Investment Committee stage has no persisted result"
            )
        return existing_result

    if stage_run.status != AnalysisStageStatus.RUNNING.value:
        raise DecisionStageStateError(
            "Only a RUNNING Investment Committee stage can be completed"
        )

    if existing_result is not None:
        raise DecisionStageStateError(
            "Investment Committee stage already has a persisted result"
        )

    payload = (
        result_data.model_dump(mode="json")
        if isinstance(result_data, BaseModel)
        else result_data
    )

    try:
        validated_result = FinalDecisionAnalysis.model_validate(payload)
    except ValidationError as exc:
        raise DecisionStageResultValidationError(
            "Investment Committee returned an invalid structured result"
        ) from exc

    analysis_result = AnalysisResult(
        analysis_run_id=stage_run.analysis_run_id,
        stage_run_id=stage_run.id,
        stage=AnalysisStage.INVESTMENT_COMMITTEE.value,
        result_data=validated_result.model_dump(mode="json"),
    )
    db.add(analysis_result)

    stage_run.status = AnalysisStageStatus.COMPLETED.value
    stage_run.completed_at = datetime.now(timezone.utc)
    stage_run.error_code = None
    stage_run.error_message = None

    db.flush()
    return analysis_result


def fail_decision_stage(
    *,
    db: Session,
    stage_run_id: UUID,
    error_code: str,
    error_message: str,
) -> AnalysisStageRun:
    stage_run = _load_stage_run_for_update(
        db=db,
        stage_run_id=stage_run_id,
    )
    _normalize_decision_stage(stage_run.stage)

    if stage_run.status == AnalysisStageStatus.FAILED.value:
        return stage_run

    if stage_run.status != AnalysisStageStatus.RUNNING.value:
        raise DecisionStageStateError(
            "Only a RUNNING Investment Committee stage can fail"
        )

    cleaned_code = error_code.strip()
    cleaned_message = error_message.strip()
    if not cleaned_code:
        raise ValueError("error_code cannot be empty")
    if len(cleaned_code) > 100:
        raise ValueError("error_code cannot exceed 100 characters")
    if not cleaned_message:
        raise ValueError("error_message cannot be empty")

    stage_run.status = AnalysisStageStatus.FAILED.value
    stage_run.error_code = cleaned_code
    stage_run.error_message = cleaned_message
    stage_run.completed_at = datetime.now(timezone.utc)

    db.flush()
    return stage_run
