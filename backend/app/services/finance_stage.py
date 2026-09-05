from datetime import (
    datetime,
    timezone,
)
from uuid import UUID

from pydantic import (
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
from app.schemas.finance_ai import (
    FinanceAssumptionBuilderContext,
)
from app.schemas.finance_runtime import (
    FinanceStageClaim,
)
from app.schemas.strategy import (
    BusinessStrategyAnalysis,
)
from app.services.research_join import (
    ResearchJoinError,
    inspect_research_join,
)


class FinanceStageError(RuntimeError):
    pass


class FinanceStageNotFoundError(
    FinanceStageError
):
    pass


class FinanceStageRunNotFoundError(
    FinanceStageError
):
    pass


class FinanceStageStateError(
    FinanceStageError
):
    pass


class FinanceStageDependencyError(
    FinanceStageError
):
    pass


def _normalize_finance_stage(
    stage: str,
) -> AnalysisStage:
    try:
        normalized_stage = (
            AnalysisStage(stage)
        )

    except ValueError as exc:
        raise FinanceStageStateError(
            f"Unknown analysis stage: {stage}"
        ) from exc

    if (
        normalized_stage
        != AnalysisStage.FINANCE
    ):
        raise FinanceStageStateError(
            "Stage is not FINANCE"
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
        raise FinanceStageNotFoundError(
            "Finance stage run not found"
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
        raise (
            FinanceStageRunNotFoundError(
                "Parent analysis run "
                "not found"
            )
        )

    if (
        analysis_run.status
        != AnalysisRunStatus.RUNNING.value
    ):
        raise FinanceStageStateError(
            "Finance cannot run unless "
            "its AnalysisRun is RUNNING"
        )

    return analysis_run


def _validate_snapshot(
    analysis_run: AnalysisRun,
) -> AnalysisProfileSnapshot:
    try:
        return (
            AnalysisProfileSnapshot
            .model_validate(
                analysis_run
                .profile_snapshot
            )
        )

    except ValidationError as exc:
        raise FinanceStageStateError(
            "Parent analysis run "
            "contains an invalid "
            "profile snapshot"
        ) from exc


def _load_business_strategy(
    *,
    db: Session,
    analysis_run_id: UUID,
) -> BusinessStrategyAnalysis:
    statement = (
        select(AnalysisResult)
        .join(
            AnalysisStageRun,
            (
                AnalysisStageRun.id
                == AnalysisResult
                .stage_run_id
            ),
        )
        .where(
            AnalysisResult.analysis_run_id
            == analysis_run_id,
            AnalysisResult.stage
            == (
                AnalysisStage
                .BUSINESS_STRATEGY
                .value
            ),
            AnalysisStageRun.stage
            == (
                AnalysisStage
                .BUSINESS_STRATEGY
                .value
            ),
            AnalysisStageRun.status
            == (
                AnalysisStageStatus
                .COMPLETED
                .value
            ),
        )
        .order_by(
            AnalysisStageRun
            .attempt
            .desc(),
            AnalysisResult
            .created_at
            .desc(),
        )
    )

    result = db.scalar(
        statement
    )

    if result is None:
        raise FinanceStageDependencyError(
            "Finance requires a "
            "completed Business Strategy "
            "result"
        )

    try:
        return (
            BusinessStrategyAnalysis
            .model_validate(
                result.result_data
            )
        )

    except ValidationError as exc:
        raise FinanceStageDependencyError(
            "Persisted Business Strategy "
            "result is invalid"
        ) from exc


def _build_finance_claim(
    *,
    db: Session,
    stage_run: AnalysisStageRun,
    analysis_run: AnalysisRun,
) -> FinanceStageClaim:
    snapshot = _validate_snapshot(
        analysis_run
    )

    business_strategy = (
        _load_business_strategy(
            db=db,
            analysis_run_id=(
                analysis_run.id
            ),
        )
    )

    try:
        research_evaluation = (
            inspect_research_join(
                db=db,
                analysis_run_id=(
                    analysis_run.id
                ),
            )
        )

    except ResearchJoinError as exc:
        raise FinanceStageDependencyError(
            "Finance cannot build its "
            "research context because "
            "Research Join is not ready"
        ) from exc

    if (
        not research_evaluation
        .gate
        .can_proceed
    ):
        raise FinanceStageDependencyError(
            "Finance cannot start before "
            "the Research Evidence Gate "
            "allows progression"
        )

    assumption_context = (
        FinanceAssumptionBuilderContext(
            profile_snapshot=snapshot,

            research_gate=(
                research_evaluation.gate
            ),

            market_analysis=(
                research_evaluation
                .results
                .get(
                    AnalysisStage
                    .MARKET_RESEARCH
                )
            ),

            competitor_analysis=(
                research_evaluation
                .results
                .get(
                    AnalysisStage
                    .COMPETITOR_INTELLIGENCE
                )
            ),

            customer_analysis=(
                research_evaluation
                .results
                .get(
                    AnalysisStage
                    .CUSTOMER_INTELLIGENCE
                )
            ),

            business_strategy=(
                business_strategy
            ),
        )
    )

    return FinanceStageClaim(
        stage_run_id=stage_run.id,
        analysis_run_id=(
            analysis_run.id
        ),
        stage=AnalysisStage.FINANCE,
        attempt=stage_run.attempt,
        assumption_context=(
            assumption_context
        ),
    )


def claim_finance_stage(
    *,
    db: Session,
    stage_run_id: UUID,
) -> FinanceStageClaim:
    stage_run = (
        _load_stage_run_for_update(
            db=db,
            stage_run_id=stage_run_id,
        )
    )

    _normalize_finance_stage(
        stage_run.stage
    )

    if (
        stage_run.status
        != AnalysisStageStatus.PENDING.value
    ):
        raise FinanceStageStateError(
            "Only a PENDING Finance "
            "stage can be claimed"
        )

    analysis_run = _load_analysis_run(
        db=db,
        analysis_run_id=(
            stage_run.analysis_run_id
        ),
    )

    claim = _build_finance_claim(
        db=db,
        stage_run=stage_run,
        analysis_run=analysis_run,
    )

    stage_run.status = (
        AnalysisStageStatus.RUNNING.value
    )

    if stage_run.started_at is None:
        stage_run.started_at = (
            datetime.now(
                timezone.utc
            )
        )

    stage_run.error_code = None
    stage_run.error_message = None

    db.flush()

    return claim