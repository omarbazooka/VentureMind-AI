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
from app.schemas.risk import RiskAnalysis
from app.schemas.risk_runtime import RiskStageClaim
from app.services.risk_context import (
    RiskContextDependencyError,
    build_risk_analysis_context,
)
from app.services.risk_grounding import (
    RiskGroundingError,
    validate_grounded_risk_analysis,
)


class RiskStageError(RuntimeError):
    pass


class RiskStageNotFoundError(RiskStageError):
    pass


class RiskStageRunNotFoundError(RiskStageError):
    pass


class RiskStageStateError(RiskStageError):
    pass


class RiskStageDependencyError(RiskStageError):
    pass


class RiskStageResultValidationError(RiskStageError):
    pass


def _normalize_risk_stage(stage: str) -> AnalysisStage:
    try:
        normalized = AnalysisStage(stage)
    except ValueError as exc:
        raise RiskStageStateError(
            f"Unknown analysis stage: {stage}"
        ) from exc

    if normalized != AnalysisStage.RISK:
        raise RiskStageStateError("Stage is not RISK")

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
        raise RiskStageNotFoundError(
            "Risk stage run not found"
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
        raise RiskStageRunNotFoundError(
            "Parent analysis run not found"
        )

    if analysis_run.status != AnalysisRunStatus.RUNNING.value:
        raise RiskStageStateError(
            "Risk cannot run unless its AnalysisRun is RUNNING"
        )

    return analysis_run


def _build_context(
    *,
    db: Session,
    analysis_run_id: UUID,
):
    try:
        return build_risk_analysis_context(
            db=db,
            analysis_run_id=analysis_run_id,
        )
    except RiskContextDependencyError as exc:
        raise RiskStageDependencyError(
            "Risk cannot build its authoritative upstream context"
        ) from exc


def claim_risk_stage(
    *,
    db: Session,
    stage_run_id: UUID,
) -> RiskStageClaim:
    stage_run = _load_stage_run_for_update(
        db=db,
        stage_run_id=stage_run_id,
    )
    _normalize_risk_stage(stage_run.stage)

    if stage_run.status != AnalysisStageStatus.PENDING.value:
        raise RiskStageStateError(
            "Only a PENDING Risk stage can be claimed"
        )

    analysis_run = _load_analysis_run(
        db=db,
        analysis_run_id=stage_run.analysis_run_id,
    )
    context = _build_context(
        db=db,
        analysis_run_id=analysis_run.id,
    )

    claim = RiskStageClaim(
        stage_run_id=stage_run.id,
        analysis_run_id=analysis_run.id,
        stage=AnalysisStage.RISK,
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


def _validate_risk_result(
    *,
    result_data: dict[str, Any] | BaseModel,
) -> RiskAnalysis:
    payload = (
        result_data.model_dump(mode="json")
        if isinstance(result_data, BaseModel)
        else result_data
    )

    try:
        return RiskAnalysis.model_validate(payload)
    except ValidationError as exc:
        raise RiskStageResultValidationError(
            "Risk returned an invalid structured result"
        ) from exc


def complete_risk_stage(
    *,
    db: Session,
    stage_run_id: UUID,
    result_data: dict[str, Any] | BaseModel,
) -> AnalysisResult:
    stage_run = _load_stage_run_for_update(
        db=db,
        stage_run_id=stage_run_id,
    )
    _normalize_risk_stage(stage_run.stage)

    existing_result = _get_existing_result(
        db=db,
        stage_run_id=stage_run.id,
    )

    if stage_run.status == AnalysisStageStatus.COMPLETED.value:
        if existing_result is None:
            raise RiskStageStateError(
                "Completed Risk stage has no persisted result"
            )
        return existing_result

    if stage_run.status != AnalysisStageStatus.RUNNING.value:
        raise RiskStageStateError(
            "Only a RUNNING Risk stage can be completed"
        )

    if existing_result is not None:
        raise RiskStageStateError(
            "Risk stage already has a persisted result"
        )

    analysis_run = _load_analysis_run(
        db=db,
        analysis_run_id=stage_run.analysis_run_id,
    )
    validated_result = _validate_risk_result(
        result_data=result_data,
    )
    context = _build_context(
        db=db,
        analysis_run_id=analysis_run.id,
    )

    try:
        validate_grounded_risk_analysis(
            analysis=validated_result,
            context=context,
        )
    except RiskGroundingError as exc:
        raise RiskStageResultValidationError(
            "Risk result failed persistence-boundary grounding validation"
        ) from exc

    analysis_result = AnalysisResult(
        analysis_run_id=stage_run.analysis_run_id,
        stage_run_id=stage_run.id,
        stage=AnalysisStage.RISK.value,
        result_data=validated_result.model_dump(mode="json"),
    )
    db.add(analysis_result)

    stage_run.status = AnalysisStageStatus.COMPLETED.value
    stage_run.completed_at = datetime.now(timezone.utc)
    stage_run.error_code = None
    stage_run.error_message = None

    db.flush()
    return analysis_result


def fail_risk_stage(
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
    _normalize_risk_stage(stage_run.stage)

    if stage_run.status == AnalysisStageStatus.FAILED.value:
        return stage_run

    if stage_run.status != AnalysisStageStatus.RUNNING.value:
        raise RiskStageStateError(
            "Only a RUNNING Risk stage can fail"
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
