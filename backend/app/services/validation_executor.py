from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.schemas.validation import ValidationDraft
from app.schemas.validation_runtime import ValidationAnalysisContext
from app.services.validation_grounding import (
    ValidationGroundingError,
    validate_grounded_validation_analysis,
)
from app.services.validation_stage import (
    ValidationStageDependencyError,
    ValidationStageResultValidationError,
    claim_validation_stage,
    complete_validation_stage,
    fail_validation_stage,
)

SessionFactory = Callable[[], Session]
ValidationRunner = Callable[[ValidationAnalysisContext], ValidationDraft]


class ValidationExecutionError(RuntimeError):
    pass


def _mark_validation_failed(
    *,
    session_factory: SessionFactory,
    stage_run_id: UUID,
    error_code: str,
    error_message: str,
) -> None:
    with session_factory() as db:
        fail_validation_stage(
            db=db,
            stage_run_id=stage_run_id,
            error_code=error_code,
            error_message=error_message,
        )
        db.commit()


def execute_validation_stage(
    *,
    session_factory: SessionFactory,
    stage_run_id: UUID,
    runner: ValidationRunner,
) -> AnalysisResult:
    with session_factory() as db:
        claim = claim_validation_stage(
            db=db,
            stage_run_id=stage_run_id,
        )
        db.commit()

    try:
        draft = runner(claim.context)
        validation_analysis = validate_grounded_validation_analysis(
            draft=draft,
            context=claim.context,
        )
    except ValidationGroundingError as exc:
        _mark_validation_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="INVALID_VALIDATION_GROUNDING",
            error_message="Validation draft failed grounding verification.",
        )
        raise ValidationExecutionError(
            "Validation grounding verification failed"
        ) from exc
    except Exception as exc:
        _mark_validation_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="VALIDATION_EXECUTION_ERROR",
            error_message=f"Validation runner raised {type(exc).__name__}.",
        )
        raise ValidationExecutionError(
            "Validation execution failed"
        ) from exc

    try:
        with session_factory() as db:
            persisted_result = complete_validation_stage(
                db=db,
                stage_run_id=stage_run_id,
                result_data=validation_analysis,
            )
            db.commit()
            return persisted_result
    except ValidationStageResultValidationError as exc:
        _mark_validation_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="INVALID_VALIDATION_RESULT",
            error_message="Validation returned an invalid structured result.",
        )
        raise ValidationExecutionError(
            "Validation returned an invalid result"
        ) from exc
    except ValidationStageDependencyError as exc:
        _mark_validation_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="VALIDATION_DEPENDENCY_CHANGED",
            error_message="Validation upstream context changed during execution.",
        )
        raise ValidationExecutionError(
            "Validation upstream context changed during execution"
        ) from exc
