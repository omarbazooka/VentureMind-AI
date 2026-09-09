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
from app.schemas.validation import ValidationAnalysis
from app.schemas.validation_runtime import ValidationStageClaim
from app.services.validation_context import (
    ValidationContextDependencyError,
    build_validation_analysis_context,
)
from app.services.validation_grounding import (
    ValidationGroundingError,
    validate_grounded_validation_analysis,
)


class ValidationStageError(RuntimeError):
    pass


class ValidationStageNotFoundError(ValidationStageError):
    pass


class ValidationStageRunNotFoundError(ValidationStageError):
    pass


class ValidationStageStateError(ValidationStageError):
    pass


class ValidationStageDependencyError(ValidationStageError):
    pass


class ValidationStageResultValidationError(ValidationStageError):
    pass


def _normalize_validation_stage(stage: str) -> AnalysisStage:
    try:
        normalized = AnalysisStage(stage)
    except ValueError as exc:
        raise ValidationStageStateError(
            f"Unknown analysis stage: {stage}"
        ) from exc

    if normalized != AnalysisStage.INDEPENDENT_VALIDATION:
        raise ValidationStageStateError("Stage is not INDEPENDENT_VALIDATION")

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
        raise ValidationStageNotFoundError(
            "Validation stage run not found"
        )

    return stage_run


def _load_analysis_run(
    *,
    db: Session,
    analysis_run_id: UUID,
) -> AnalysisRun:
    analysis_run = db.get(AnalysisRun, analysis_run_id)
    if analysis_run is None:
        raise ValidationStageRunNotFoundError(
            "Parent analysis run not found"
        )

    if analysis_run.status != AnalysisRunStatus.RUNNING.value:
        raise ValidationStageStateError(
            "Validation cannot run unless its AnalysisRun is RUNNING"
        )

    return analysis_run


def claim_validation_stage(
    *,
    db: Session,
    stage_run_id: UUID,
) -> ValidationStageClaim:
    stage_run = _load_stage_run_for_update(
        db=db,
        stage_run_id=stage_run_id,
    )
    _normalize_validation_stage(stage_run.stage)

    if stage_run.status != AnalysisStageStatus.PENDING.value:
        raise ValidationStageStateError(
            "Only a PENDING Validation stage can be claimed"
        )

    analysis_run = _load_analysis_run(
        db=db,
        analysis_run_id=stage_run.analysis_run_id,
    )
    try:
        context = build_validation_analysis_context(
            db=db,
            analysis_run_id=analysis_run.id,
        )
    except ValidationContextDependencyError as exc:
        raise ValidationStageDependencyError(
            "Validation cannot build its authoritative upstream context"
        ) from exc

    claim = ValidationStageClaim(
        stage_run_id=stage_run.id,
        analysis_run_id=analysis_run.id,
        stage=AnalysisStage.INDEPENDENT_VALIDATION,
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


def complete_validation_stage(
    *,
    db: Session,
    stage_run_id: UUID,
    result_data: dict[str, Any] | BaseModel,
) -> AnalysisResult:
    stage_run = _load_stage_run_for_update(
        db=db,
        stage_run_id=stage_run_id,
    )
    _normalize_validation_stage(stage_run.stage)

    existing_result = _get_existing_result(
        db=db,
        stage_run_id=stage_run.id,
    )

    if stage_run.status == AnalysisStageStatus.COMPLETED.value:
        if existing_result is None:
            raise ValidationStageStateError(
                "Completed Validation stage has no persisted result"
            )
        return existing_result

    if stage_run.status != AnalysisStageStatus.RUNNING.value:
        raise ValidationStageStateError(
            "Only a RUNNING Validation stage can be completed"
        )

    if existing_result is not None:
        raise ValidationStageStateError(
            "Validation stage already has a persisted result"
        )

    payload = (
        result_data.model_dump(mode="json")
        if isinstance(result_data, BaseModel)
        else result_data
    )

    try:
        validated_result = ValidationAnalysis.model_validate(payload)
    except ValidationError as exc:
        raise ValidationStageResultValidationError(
            "Validation returned an invalid structured result"
        ) from exc

    analysis_result = AnalysisResult(
        analysis_run_id=stage_run.analysis_run_id,
        stage_run_id=stage_run.id,
        stage=AnalysisStage.INDEPENDENT_VALIDATION.value,
        result_data=validated_result.model_dump(mode="json"),
    )
    db.add(analysis_result)

    stage_run.status = AnalysisStageStatus.COMPLETED.value
    stage_run.completed_at = datetime.now(timezone.utc)
    stage_run.error_code = None
    stage_run.error_message = None

    db.flush()
    return analysis_result


def fail_validation_stage(
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
    _normalize_validation_stage(stage_run.stage)

    if stage_run.status == AnalysisStageStatus.FAILED.value:
        return stage_run

    if stage_run.status != AnalysisStageStatus.RUNNING.value:
        raise ValidationStageStateError(
            "Only a RUNNING Validation stage can fail"
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
