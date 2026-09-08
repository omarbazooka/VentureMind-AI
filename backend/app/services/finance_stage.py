from datetime import (
    datetime,
    timezone,
)
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
from app.models.analysis_run_input import (
    AnalysisRunInput,
)
from app.models.analysis_stage_run import (
    AnalysisStageRun,
)
from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisRunInputStatus,
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.finance import (
    FinancialScenarioBundle,
)
from app.schemas.finance_ai import (
    FinanceAssumptionBuilderContext,
)
from app.schemas.finance_runtime import (
    FinanceInputRequest,
    FinanceStageClaim,
    FinanceUserAnswerMode,
    FinanceUserInputAnswer,
    ResolvedFinanceUserInput,
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


class FinanceStageResultValidationError(
    FinanceStageError
):
    pass


def _normalize_finance_stage(
    stage: str,
) -> AnalysisStage:
    try:
        normalized_stage = AnalysisStage(stage)
    except ValueError as exc:
        raise FinanceStageStateError(
            f"Unknown analysis stage: {stage}"
        ) from exc

    if normalized_stage != AnalysisStage.FINANCE:
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

    stage_run = db.scalar(statement)

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
        raise FinanceStageRunNotFoundError(
            "Parent analysis run not found"
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


def _load_analysis_run_for_update(
    *,
    db: Session,
    analysis_run_id: UUID,
) -> AnalysisRun:
    statement = (
        select(AnalysisRun)
        .where(
            AnalysisRun.id
            == analysis_run_id
        )
        .with_for_update()
    )

    analysis_run = db.scalar(statement)

    if analysis_run is None:
        raise FinanceStageRunNotFoundError(
            "Parent analysis run not found"
        )

    return analysis_run


def _validate_snapshot(
    analysis_run: AnalysisRun,
) -> AnalysisProfileSnapshot:
    try:
        return AnalysisProfileSnapshot.model_validate(
            analysis_run.profile_snapshot
        )
    except ValidationError as exc:
        raise FinanceStageStateError(
            "Parent analysis run contains an "
            "invalid profile snapshot"
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
            AnalysisStageRun.id
            == AnalysisResult.stage_run_id,
        )
        .where(
            AnalysisResult.analysis_run_id
            == analysis_run_id,
            AnalysisResult.stage
            == AnalysisStage.BUSINESS_STRATEGY.value,
            AnalysisStageRun.stage
            == AnalysisStage.BUSINESS_STRATEGY.value,
            AnalysisStageRun.status
            == AnalysisStageStatus.COMPLETED.value,
        )
        .order_by(
            AnalysisStageRun.attempt.desc(),
            AnalysisResult.created_at.desc(),
        )
    )

    result = db.scalar(statement)

    if result is None:
        raise FinanceStageDependencyError(
            "Finance requires a completed "
            "Business Strategy result"
        )

    try:
        return BusinessStrategyAnalysis.model_validate(
            result.result_data
        )
    except ValidationError as exc:
        raise FinanceStageDependencyError(
            "Persisted Business Strategy result "
            "is invalid"
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
    business_strategy = _load_business_strategy(
        db=db,
        analysis_run_id=analysis_run.id,
    )

    try:
        research_evaluation = inspect_research_join(
            db=db,
            analysis_run_id=analysis_run.id,
        )
    except ResearchJoinError as exc:
        raise FinanceStageDependencyError(
            "Finance cannot build its research "
            "context because Research Join is "
            "not ready"
        ) from exc

    if not research_evaluation.gate.can_proceed:
        raise FinanceStageDependencyError(
            "Finance cannot start before the "
            "Research Evidence Gate allows "
            "progression"
        )

    assumption_context = FinanceAssumptionBuilderContext(
        profile_snapshot=snapshot,
        research_gate=research_evaluation.gate,
        market_analysis=(
            research_evaluation.results.get(
                AnalysisStage.MARKET_RESEARCH
            )
        ),
        competitor_analysis=(
            research_evaluation.results.get(
                AnalysisStage.COMPETITOR_INTELLIGENCE
            )
        ),
        customer_analysis=(
            research_evaluation.results.get(
                AnalysisStage.CUSTOMER_INTELLIGENCE
            )
        ),
        business_strategy=business_strategy,
    )

    return FinanceStageClaim(
        stage_run_id=stage_run.id,
        analysis_run_id=analysis_run.id,
        stage=AnalysisStage.FINANCE,
        attempt=stage_run.attempt,
        assumption_context=assumption_context,
    )


def claim_finance_stage(
    *,
    db: Session,
    stage_run_id: UUID,
) -> FinanceStageClaim:
    stage_run = _load_stage_run_for_update(
        db=db,
        stage_run_id=stage_run_id,
    )

    _normalize_finance_stage(
        stage_run.stage
    )

    if (
        stage_run.status
        != AnalysisStageStatus.PENDING.value
    ):
        raise FinanceStageStateError(
            "Only a PENDING Finance stage "
            "can be claimed"
        )

    analysis_run = _load_analysis_run(
        db=db,
        analysis_run_id=stage_run.analysis_run_id,
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
        stage_run.started_at = datetime.now(
            timezone.utc
        )

    stage_run.error_code = None
    stage_run.error_message = None

    db.flush()

    return claim


def _get_pending_finance_input(
    *,
    db: Session,
    stage_run_id: UUID,
) -> AnalysisRunInput | None:
    statement = (
        select(AnalysisRunInput)
        .where(
            AnalysisRunInput.stage_run_id
            == stage_run_id,
            AnalysisRunInput.status
            == AnalysisRunInputStatus.PENDING.value,
        )
        .order_by(
            AnalysisRunInput.created_at.desc()
        )
    )

    return db.scalar(statement)


def _load_run_input_for_update(
    *,
    db: Session,
    run_input_id: UUID,
) -> AnalysisRunInput:
    statement = (
        select(AnalysisRunInput)
        .where(
            AnalysisRunInput.id
            == run_input_id
        )
        .with_for_update()
    )

    run_input = db.scalar(statement)

    if run_input is None:
        raise FinanceStageNotFoundError(
            "Analysis run input not found"
        )

    return run_input


def pause_finance_for_user_input(
    *,
    db: Session,
    stage_run_id: UUID,
    request: FinanceInputRequest,
) -> AnalysisRunInput:
    stage_run = _load_stage_run_for_update(
        db=db,
        stage_run_id=stage_run_id,
    )

    _normalize_finance_stage(
        stage_run.stage
    )

    if (
        stage_run.status
        != AnalysisStageStatus.RUNNING.value
    ):
        raise FinanceStageStateError(
            "Only a RUNNING Finance stage "
            "can pause for user input"
        )

    analysis_run = _load_analysis_run_for_update(
        db=db,
        analysis_run_id=stage_run.analysis_run_id,
    )

    if (
        analysis_run.status
        != AnalysisRunStatus.RUNNING.value
    ):
        raise FinanceStageStateError(
            "Finance can only pause a RUNNING "
            "AnalysisRun"
        )

    existing_pending = _get_pending_finance_input(
        db=db,
        stage_run_id=stage_run.id,
    )

    if existing_pending is not None:
        raise FinanceStageStateError(
            "Finance already has a pending "
            "user input request"
        )

    run_input = AnalysisRunInput(
        analysis_run_id=analysis_run.id,
        stage_run_id=stage_run.id,
        input_name=request.input_name.value,
        status=AnalysisRunInputStatus.PENDING.value,
        request_data=request.model_dump(
            mode="json"
        ),
        response_data=None,
    )

    db.add(run_input)

    stage_run.status = (
        AnalysisStageStatus.PAUSED_FOR_USER.value
    )
    analysis_run.status = (
        AnalysisRunStatus.PAUSED_FOR_USER.value
    )

    stage_run.error_code = None
    stage_run.error_message = None
    analysis_run.error_code = None
    analysis_run.error_message = None

    db.flush()

    return run_input


def _resolve_finance_user_answer(
    *,
    run_input: AnalysisRunInput,
    answer: FinanceUserInputAnswer,
) -> ResolvedFinanceUserInput:
    try:
        request = FinanceInputRequest.model_validate(
            run_input.request_data
        )
    except ValidationError as exc:
        raise FinanceStageStateError(
            "Persisted Finance input request "
            "is invalid"
        ) from exc

    if request.input_name.value != run_input.input_name:
        raise FinanceStageStateError(
            "Persisted Finance request does not "
            "match its input_name column"
        )

    if answer.input_name != request.input_name:
        raise FinanceStageStateError(
            "Finance answer does not match the "
            "requested input"
        )

    if (
        answer.answer_mode
        == FinanceUserAnswerMode.SELECTED_OPTION
    ):
        selected = next(
            (
                option
                for option in request.options
                if option.option_id
                == answer.selected_option_id
            ),
            None,
        )

        if selected is None:
            raise FinanceStageStateError(
                "Selected Finance option does not "
                "exist in the persisted request"
            )

        return ResolvedFinanceUserInput(
            input_name=selected.input_name,
            answer_mode=answer.answer_mode,
            selected_option_id=selected.option_id,
            value=selected.value,
            currency=selected.currency,
            unit_label=selected.unit_label,
            period=selected.period,
        )

    if (
        request.currency is not None
        and answer.currency != request.currency
    ):
        raise FinanceStageStateStateError(
            "Custom Finance answer currency must "
            "match the requested currency"
        )

    if (
        request.unit_label is not None
        and answer.unit_label != request.unit_label
    ):
        raise FinanceStageStateError(
            "Custom Finance answer unit must "
            "match the requested unit"
        )

    if (
        request.period is not None
        and answer.period != request.period
    ):
        raise FinanceStageStateError(
            "Custom Finance answer period must "
            "match the requested period"
        )

    if answer.value is None:
        raise FinanceStageStateError(
            "Custom Finance answer has no value"
        )

    return ResolvedFinanceUserInput(
        input_name=answer.input_name,
        answer_mode=answer.answer_mode,
        value=answer.value,
        currency=answer.currency,
        unit_label=answer.unit_label,
        period=answer.period,
    )


def answer_finance_user_input(
    *,
    db: Session,
    run_input_id: UUID,
    answer: FinanceUserInputAnswer,
    source_message_id: UUID | None = None,
) -> AnalysisRunInput:
    run_input = _load_run_input_for_update(
        db=db,
        run_input_id=run_input_id,
    )

    if (
        run_input.status
        != AnalysisRunInputStatus.PENDING.value
    ):
        raise FinanceStageStateError(
            "Only a PENDING analysis input "
            "can be answered"
        )

    stage_run = _load_stage_run_for_update(
        db=db,
        stage_run_id=run_input.stage_run_id,
    )

    _normalize_finance_stage(
        stage_run.stage
    )

    if (
        stage_run.status
        != AnalysisStageStatus.PAUSED_FOR_USER.value
    ):
        raise FinanceStageStateError(
            "Finance stage is not paused for "
            "user input"
        )

    analysis_run = _load_analysis_run_for_update(
        db=db,
        analysis_run_id=run_input.analysis_run_id,
    )

    if (
        analysis_run.status
        != AnalysisRunStatus.PAUSED_FOR_USER.value
    ):
        raise FinanceStageStateError(
            "Parent AnalysisRun is not paused "
            "for user input"
        )

    if (
        stage_run.analysis_run_id
        != run_input.analysis_run_id
    ):
        raise FinanceStageStateError(
            "Analysis input does not belong to "
            "the Finance stage's AnalysisRun"
        )

    resolved = _resolve_finance_user_answer(
        run_input=run_input,
        answer=answer,
    )

    run_input.response_data = resolved.model_dump(
        mode="json"
    )
    run_input.source_message_id = source_message_id
    run_input.status = (
        AnalysisRunInputStatus.ANSWERED.value
    )
    run_input.answered_at = datetime.now(
        timezone.utc
    )

    # An answered pause is ready to be claimed again.
    # RUNNING is reserved for an executor that has
    # actually acquired the stage.
    stage_run.status = (
        AnalysisStageStatus.PENDING.value
    )
    analysis_run.status = (
        AnalysisRunStatus.RUNNING.value
    )

    stage_run.error_code = None
    stage_run.error_message = None
    analysis_run.error_code = None
    analysis_run.error_message = None

    db.flush()

    return run_input


def load_answered_finance_inputs(
    *,
    db: Session,
    stage_run_id: UUID,
) -> list[AnalysisRunInput]:
    statement = (
        select(AnalysisRunInput)
        .where(
            AnalysisRunInput.stage_run_id
            == stage_run_id,
            AnalysisRunInput.status
            == AnalysisRunInputStatus.ANSWERED.value,
        )
        .order_by(
            AnalysisRunInput.answered_at.asc(),
            AnalysisRunInput.created_at.asc(),
        )
    )

    return list(
        db.scalars(statement).all()
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

    return db.scalar(statement)


def _validate_finance_result(
    *,
    result_data: dict[str, Any] | BaseModel,
) -> FinancialScenarioBundle:
    if isinstance(result_data, BaseModel):
        payload = result_data.model_dump(
            mode="json"
        )
    else:
        payload = result_data

    try:
        return FinancialScenarioBundle.model_validate(
            payload
        )
    except ValidationError as exc:
        raise FinanceStageResultValidationError(
            "Finance returned an invalid "
            "structured result"
        ) from exc


def complete_finance_stage(
    *,
    db: Session,
    stage_run_id: UUID,
    result_data: dict[str, Any] | BaseModel,
) -> AnalysisResult:
    stage_run = _load_stage_run_for_update(
        db=db,
        stage_run_id=stage_run_id,
    )

    _normalize_finance_stage(
        stage_run.stage
    )

    existing_result = _get_existing_result(
        db=db,
        stage_run_id=stage_run.id,
    )

    if (
        stage_run.status
        == AnalysisStageStatus.COMPLETED.value
    ):
        if existing_result is None:
            raise FinanceStageStateError(
                "Completed Finance stage has no "
                "persisted result"
            )
        return existing_result

    if (
        stage_run.status
        != AnalysisStageStatus.RUNNING.value
    ):
        raise FinanceStageStateError(
            "Only a RUNNING Finance stage "
            "can be completed"
        )

    if existing_result is not None:
        raise FinanceStageStateError(
            "Finance stage already has a "
            "persisted result"
        )

    _load_analysis_run(
        db=db,
        analysis_run_id=stage_run.analysis_run_id,
    )

    validated_result = _validate_finance_result(
        result_data=result_data,
    )

    analysis_result = AnalysisResult(
        analysis_run_id=stage_run.analysis_run_id,
        stage_run_id=stage_run.id,
        stage=AnalysisStage.FINANCE.value,
        result_data=validated_result.model_dump(
            mode="json"
        ),
    )

    db.add(analysis_result)

    stage_run.status = (
        AnalysisStageStatus.COMPLETED.value
    )
    stage_run.completed_at = datetime.now(
        timezone.utc
    )
    stage_run.error_code = None
    stage_run.error_message = None

    db.flush()

    return analysis_result


def fail_finance_stage(
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

    _normalize_finance_stage(
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
        raise FinanceStageStateError(
            "Only a RUNNING Finance stage "
            "can fail"
        )

    cleaned_code = error_code.strip()
    cleaned_message = error_message.strip()

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
    stage_run.error_message = cleaned_message
    stage_run.completed_at = datetime.now(
        timezone.utc
    )

    db.flush()

    return stage_run
