from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.schemas.decision import FinalDecisionDraft
from app.schemas.decision_runtime import InvestmentCommitteeContext
from app.services.decision_grounding import (
    DecisionGroundingError,
    validate_grounded_decision,
)
from app.services.decision_stage import (
    DecisionStageDependencyError,
    DecisionStageResultValidationError,
    claim_decision_stage,
    complete_decision_stage,
    fail_decision_stage,
)

SessionFactory = Callable[[], Session]
DecisionRunner = Callable[[InvestmentCommitteeContext], FinalDecisionDraft]


class DecisionExecutionError(RuntimeError):
    pass


def _mark_decision_failed(
    *,
    session_factory: SessionFactory,
    stage_run_id: UUID,
    error_code: str,
    error_message: str,
) -> None:
    with session_factory() as db:
        fail_decision_stage(
            db=db,
            stage_run_id=stage_run_id,
            error_code=error_code,
            error_message=error_message,
        )
        db.commit()


def execute_decision_stage(
    *,
    session_factory: SessionFactory,
    stage_run_id: UUID,
    runner: DecisionRunner,
) -> AnalysisResult:
    with session_factory() as db:
        claim = claim_decision_stage(
            db=db,
            stage_run_id=stage_run_id,
        )
        db.commit()

    try:
        draft = runner(claim.context)
        decision_analysis = validate_grounded_decision(
            draft=draft,
            context=claim.context,
        )
    except DecisionGroundingError as exc:
        _mark_decision_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="INVALID_DECISION_GROUNDING",
            error_message="Investment Committee draft failed grounding verification.",
        )
        raise DecisionExecutionError(
            "Investment Committee grounding verification failed"
        ) from exc
    except Exception as exc:
        _mark_decision_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="DECISION_EXECUTION_ERROR",
            error_message=f"Investment Committee runner raised {type(exc).__name__}.",
        )
        raise DecisionExecutionError(
            "Investment Committee execution failed"
        ) from exc

    try:
        with session_factory() as db:
            persisted_result = complete_decision_stage(
                db=db,
                stage_run_id=stage_run_id,
                result_data=decision_analysis,
            )
            db.commit()
            return persisted_result
    except DecisionStageResultValidationError as exc:
        _mark_decision_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="INVALID_DECISION_RESULT",
            error_message="Investment Committee returned an invalid structured result.",
        )
        raise DecisionExecutionError(
            "Investment Committee returned an invalid result"
        ) from exc
    except DecisionStageDependencyError as exc:
        _mark_decision_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="DECISION_DEPENDENCY_CHANGED",
            error_message="Investment Committee upstream context changed during execution.",
        )
        raise DecisionExecutionError(
            "Investment Committee upstream context changed during execution"
        ) from exc
