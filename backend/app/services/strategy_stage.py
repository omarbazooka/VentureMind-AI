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
from app.schemas.strategy import (
    BusinessStrategyAnalysis,
    StrategyStageClaim,
)
from app.services.research_join import (
    ResearchJoinError,
    inspect_research_join,
)
from app.services.strategy_grounding import (
    StrategyGroundingError,
    finalize_business_strategy,
)


class StrategyStageError(RuntimeError):
    pass


class StrategyStageNotFoundError(
    StrategyStageError
):
    pass


class StrategyStageRunNotFoundError(
    StrategyStageError
):
    pass


class StrategyStageStateError(
    StrategyStageError
):
    pass


class StrategyStageResultValidationError(
    StrategyStageError
):
    pass


def _normalize_strategy_stage(
    stage: str,
) -> AnalysisStage:
    try:
        normalized_stage = AnalysisStage(
            stage
        )
    except ValueError as exc:
        raise StrategyStageStateError(
            f"Unknown analysis stage: {stage}"
        ) from exc

    if (
        normalized_stage
        != AnalysisStage.BUSINESS_STRATEGY
    ):
        raise StrategyStageStateError(
            "Stage is not BUSINESS_STRATEGY"
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
        raise StrategyStageNotFoundError(
            "Business Strategy stage run "
            "not found"
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
        raise StrategyStageRunNotFoundError(
            "Parent analysis run not found"
        )

    if (
        analysis_run.status
        != AnalysisRunStatus.RUNNING.value
    ):
        raise StrategyStageStateError(
            "Business Strategy cannot run "
            "unless its AnalysisRun is RUNNING"
        )

    return analysis_run


def _validate_snapshot(
    analysis_run: AnalysisRun,
) -> AnalysisProfileSnapshot:
    try:
        return (
            AnalysisProfileSnapshot
            .model_validate(
                analysis_run.profile_snapshot
            )
        )
    except ValidationError as exc:
        raise StrategyStageStateError(
            "Parent analysis run contains "
            "an invalid profile snapshot"
        ) from exc


def _build_strategy_claim(
    *,
    db: Session,
    stage_run: AnalysisStageRun,
    analysis_run: AnalysisRun,
) -> StrategyStageClaim:
    snapshot = _validate_snapshot(
        analysis_run
    )

    try:
        evaluation = inspect_research_join(
            db=db,
            analysis_run_id=(
                analysis_run.id
            ),
        )
    except ResearchJoinError as exc:
        raise StrategyStageStateError(
            "Business Strategy cannot build "
            "its research context because "
            "Research Join is not ready"
        ) from exc

    if not evaluation.gate.can_proceed:
        raise StrategyStageStateError(
            "Business Strategy cannot start "
            "before the Research Evidence "
            "Gate allows progression"
        )

    return StrategyStageClaim(
        stage_run_id=stage_run.id,
        analysis_run_id=analysis_run.id,
        stage=(
            AnalysisStage.BUSINESS_STRATEGY
        ),
        attempt=stage_run.attempt,
        profile_snapshot=snapshot,
        research_gate=evaluation.gate,
        market_analysis=(
            evaluation.results.get(
                AnalysisStage.MARKET_RESEARCH
            )
        ),
        competitor_analysis=(
            evaluation.results.get(
                AnalysisStage
                .COMPETITOR_INTELLIGENCE
            )
        ),
        customer_analysis=(
            evaluation.results.get(
                AnalysisStage
                .CUSTOMER_INTELLIGENCE
            )
        ),
    )


def claim_strategy_stage(
    *,
    db: Session,
    stage_run_id: UUID,
) -> StrategyStageClaim:
    stage_run = (
        _load_stage_run_for_update(
            db=db,
            stage_run_id=stage_run_id,
        )
    )

    _normalize_strategy_stage(
        stage_run.stage
    )

    if (
        stage_run.status
        != AnalysisStageStatus.PENDING.value
    ):
        raise StrategyStageStateError(
            "Only a PENDING Business Strategy "
            "stage can be claimed"
        )

    analysis_run = _load_analysis_run(
        db=db,
        analysis_run_id=(
            stage_run.analysis_run_id
        ),
    )

    claim = _build_strategy_claim(
        db=db,
        stage_run=stage_run,
        analysis_run=analysis_run,
    )

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

    return claim


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


def _validate_strategy_result(
    *,
    result_data: (
        dict[str, Any]
        | BaseModel
    ),
) -> BusinessStrategyAnalysis:
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
        return (
            BusinessStrategyAnalysis
            .model_validate(
                payload
            )
        )
    except ValidationError as exc:
        raise (
            StrategyStageResultValidationError(
                "Business Strategy returned "
                "an invalid structured result"
            )
        ) from exc


def complete_strategy_stage(
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

    _normalize_strategy_stage(
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
            raise StrategyStageStateError(
                "Completed Business Strategy "
                "stage has no persisted result"
            )

        return existing_result

    if (
        stage_run.status
        != AnalysisStageStatus.RUNNING.value
    ):
        raise StrategyStageStateError(
            "Only a RUNNING Business Strategy "
            "stage can be completed"
        )

    if existing_result is not None:
        raise StrategyStageStateError(
            "Business Strategy stage already "
            "has a persisted result"
        )

    analysis_run = _load_analysis_run(
        db=db,
        analysis_run_id=(
            stage_run.analysis_run_id
        ),
    )

    authoritative_claim = (
        _build_strategy_claim(
            db=db,
            stage_run=stage_run,
            analysis_run=analysis_run,
        )
    )

    validated_result = (
        _validate_strategy_result(
            result_data=result_data,
        )
    )

    try:
        grounded_result = (
            finalize_business_strategy(
                analysis=validated_result,
                claim=authoritative_claim,
            )
        )
    except StrategyGroundingError as exc:
        raise (
            StrategyStageResultValidationError(
                "Business Strategy result "
                "failed deterministic grounding"
            )
        ) from exc

    analysis_result = AnalysisResult(
        analysis_run_id=(
            stage_run.analysis_run_id
        ),
        stage_run_id=stage_run.id,
        stage=(
            AnalysisStage
            .BUSINESS_STRATEGY
            .value
        ),
        result_data=(
            grounded_result.model_dump(
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


def fail_strategy_stage(
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

    _normalize_strategy_stage(
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
        raise StrategyStageStateError(
            "Only a RUNNING Business Strategy "
            "stage can fail"
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