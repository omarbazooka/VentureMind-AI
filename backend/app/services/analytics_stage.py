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
from app.schemas.analytics import DecisionAnalyticsResult
from app.schemas.analytics_runtime import AnalyticsStageClaim
from app.schemas.finance import FinancialScenarioBundle


class AnalyticsStageError(RuntimeError):
    pass


class AnalyticsStageNotFoundError(AnalyticsStageError):
    pass


class AnalyticsStageRunNotFoundError(AnalyticsStageError):
    pass


class AnalyticsStageStateError(AnalyticsStageError):
    pass


class AnalyticsStageDependencyError(AnalyticsStageError):
    pass


class AnalyticsStageResultValidationError(AnalyticsStageError):
    pass


def _normalize_analytics_stage(stage: str) -> AnalysisStage:
    try:
        normalized = AnalysisStage(stage)
    except ValueError as exc:
        raise AnalyticsStageStateError(
            f"Unknown analysis stage: {stage}"
        ) from exc

    if normalized != AnalysisStage.DECISION_ANALYTICS:
        raise AnalyticsStageStateError(
            "Stage is not DECISION_ANALYTICS"
        )

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
        raise AnalyticsStageNotFoundError(
            "Decision Analytics stage run not found"
        )

    return stage_run


def _load_analysis_run(
    *,
    db: Session,
    analysis_run_id: UUID,
) -> AnalysisRun:
    analysis_run = db.get(AnalysisRun, analysis_run_id)

    if analysis_run is None:
        raise AnalyticsStageRunNotFoundError(
            "Parent analysis run not found"
        )

    if analysis_run.status != AnalysisRunStatus.RUNNING.value:
        raise AnalyticsStageStateError(
            "Decision Analytics cannot run unless its AnalysisRun is RUNNING"
        )

    return analysis_run


def _load_completed_finance_result(
    *,
    db: Session,
    analysis_run_id: UUID,
) -> tuple[AnalysisResult, FinancialScenarioBundle]:
    statement = (
        select(AnalysisResult)
        .join(
            AnalysisStageRun,
            AnalysisStageRun.id == AnalysisResult.stage_run_id,
        )
        .where(
            AnalysisResult.analysis_run_id == analysis_run_id,
            AnalysisResult.stage == AnalysisStage.FINANCE.value,
            AnalysisStageRun.stage == AnalysisStage.FINANCE.value,
            AnalysisStageRun.status == AnalysisStageStatus.COMPLETED.value,
        )
        .order_by(
            AnalysisStageRun.attempt.desc(),
            AnalysisResult.created_at.desc(),
        )
    )
    result = db.scalar(statement)

    if result is None:
        raise AnalyticsStageDependencyError(
            "Decision Analytics requires a completed Finance result"
        )

    try:
        bundle = FinancialScenarioBundle.model_validate(
            result.result_data
        )
    except ValidationError as exc:
        raise AnalyticsStageDependencyError(
            "Persisted Finance result is invalid"
        ) from exc

    return result, bundle


def claim_analytics_stage(
    *,
    db: Session,
    stage_run_id: UUID,
) -> AnalyticsStageClaim:
    stage_run = _load_stage_run_for_update(
        db=db,
        stage_run_id=stage_run_id,
    )
    _normalize_analytics_stage(stage_run.stage)

    if stage_run.status != AnalysisStageStatus.PENDING.value:
        raise AnalyticsStageStateError(
            "Only a PENDING Decision Analytics stage can be claimed"
        )

    analysis_run = _load_analysis_run(
        db=db,
        analysis_run_id=stage_run.analysis_run_id,
    )
    finance_result, finance_bundle = _load_completed_finance_result(
        db=db,
        analysis_run_id=analysis_run.id,
    )

    claim = AnalyticsStageClaim(
        stage_run_id=stage_run.id,
        analysis_run_id=analysis_run.id,
        stage=AnalysisStage.DECISION_ANALYTICS,
        attempt=stage_run.attempt,
        finance_stage_run_id=finance_result.stage_run_id,
        finance_bundle=finance_bundle,
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
    statement = select(AnalysisResult).where(
        AnalysisResult.stage_run_id == stage_run_id
    )
    return db.scalar(statement)


def _validate_analytics_result(
    *,
    result_data: dict[str, Any] | BaseModel,
) -> DecisionAnalyticsResult:
    payload = (
        result_data.model_dump(mode="json")
        if isinstance(result_data, BaseModel)
        else result_data
    )

    try:
        return DecisionAnalyticsResult.model_validate(payload)
    except ValidationError as exc:
        raise AnalyticsStageResultValidationError(
            "Decision Analytics returned an invalid structured result"
        ) from exc


def complete_analytics_stage(
    *,
    db: Session,
    stage_run_id: UUID,
    result_data: dict[str, Any] | BaseModel,
) -> AnalysisResult:
    stage_run = _load_stage_run_for_update(
        db=db,
        stage_run_id=stage_run_id,
    )
    _normalize_analytics_stage(stage_run.stage)

    existing_result = _get_existing_result(
        db=db,
        stage_run_id=stage_run.id,
    )

    if stage_run.status == AnalysisStageStatus.COMPLETED.value:
        if existing_result is None:
            raise AnalyticsStageStateError(
                "Completed Decision Analytics stage has no persisted result"
            )
        return existing_result

    if stage_run.status != AnalysisStageStatus.RUNNING.value:
        raise AnalyticsStageStateError(
            "Only a RUNNING Decision Analytics stage can be completed"
        )

    if existing_result is not None:
        raise AnalyticsStageStateError(
            "Decision Analytics stage already has a persisted result"
        )

    _load_analysis_run(
        db=db,
        analysis_run_id=stage_run.analysis_run_id,
    )

    validated_result = _validate_analytics_result(
        result_data=result_data
    )
    finance_result, _ = _load_completed_finance_result(
        db=db,
        analysis_run_id=stage_run.analysis_run_id,
    )

    if validated_result.finance_stage_run_id != finance_result.stage_run_id:
        raise AnalyticsStageResultValidationError(
            "Decision Analytics result does not reference the active completed Finance result"
        )

    analysis_result = AnalysisResult(
        analysis_run_id=stage_run.analysis_run_id,
        stage_run_id=stage_run.id,
        stage=AnalysisStage.DECISION_ANALYTICS.value,
        result_data=validated_result.model_dump(mode="json"),
    )
    db.add(analysis_result)

    stage_run.status = AnalysisStageStatus.COMPLETED.value
    stage_run.completed_at = datetime.now(timezone.utc)
    stage_run.error_code = None
    stage_run.error_message = None

    db.flush()
    return analysis_result


def fail_analytics_stage(
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
    _normalize_analytics_stage(stage_run.stage)

    if stage_run.status == AnalysisStageStatus.FAILED.value:
        return stage_run

    if stage_run.status != AnalysisStageStatus.RUNNING.value:
        raise AnalyticsStageStateError(
            "Only a RUNNING Decision Analytics stage can fail"
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
