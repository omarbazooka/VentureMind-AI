from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.schemas.risk import RiskDraftAnalysis
from app.schemas.risk_runtime import RiskAnalysisContext
from app.services.risk_grounding import (
    RiskGroundingError,
    finalize_risk_analysis,
)
from app.services.risk_stage import (
    RiskStageDependencyError,
    RiskStageResultValidationError,
    claim_risk_stage,
    complete_risk_stage,
    fail_risk_stage,
)


SessionFactory = Callable[[], Session]
RiskRunner = Callable[[RiskAnalysisContext], RiskDraftAnalysis]


class RiskExecutionError(RuntimeError):
    pass


def _mark_risk_failed(
    *,
    session_factory: SessionFactory,
    stage_run_id: UUID,
    error_code: str,
    error_message: str,
) -> None:
    with session_factory() as db:
        fail_risk_stage(
            db=db,
            stage_run_id=stage_run_id,
            error_code=error_code,
            error_message=error_message,
        )
        db.commit()


def execute_risk_stage(
    *,
    session_factory: SessionFactory,
    stage_run_id: UUID,
    runner: RiskRunner,
) -> AnalysisResult:
    with session_factory() as db:
        claim = claim_risk_stage(
            db=db,
            stage_run_id=stage_run_id,
        )
        db.commit()

    try:
        draft = runner(claim.context)
        risk_analysis = finalize_risk_analysis(
            draft=draft,
            context=claim.context,
        )

    except RiskGroundingError as exc:
        _mark_risk_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="INVALID_RISK_GROUNDING",
            error_message=(
                "Risk draft failed deterministic grounding validation."
            ),
        )
        raise RiskExecutionError(
            "Risk grounding verification failed"
        ) from exc

    except Exception as exc:
        _mark_risk_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="RISK_EXECUTION_ERROR",
            error_message=(
                "Risk runner raised "
                f"{type(exc).__name__}."
            ),
        )
        raise RiskExecutionError(
            "Risk execution failed"
        ) from exc

    try:
        with session_factory() as db:
            persisted_result = complete_risk_stage(
                db=db,
                stage_run_id=stage_run_id,
                result_data=risk_analysis,
            )
            db.commit()
            return persisted_result

    except RiskStageResultValidationError as exc:
        _mark_risk_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="INVALID_RISK_RESULT",
            error_message=(
                "Risk returned an invalid or ungrounded structured result."
            ),
        )
        raise RiskExecutionError(
            "Risk returned an invalid result"
        ) from exc

    except RiskStageDependencyError as exc:
        _mark_risk_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="RISK_DEPENDENCY_CHANGED",
            error_message=(
                "Risk upstream context became invalid before persistence."
            ),
        )
        raise RiskExecutionError(
            "Risk upstream context changed during execution"
        ) from exc
