from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.analytics.builder import build_decision_analytics_result
from app.analytics.comparisons import DecisionAnalyticsComparisonError
from app.analytics.sensitivity import DecisionSensitivityError
from app.models.analysis_result import AnalysisResult
from app.services.analytics_stage import (
    AnalyticsStageResultValidationError,
    claim_analytics_stage,
    complete_analytics_stage,
    fail_analytics_stage,
)


SessionFactory = Callable[[], Session]


class AnalyticsExecutionError(RuntimeError):
    pass


def _mark_analytics_failed(
    *,
    session_factory: SessionFactory,
    stage_run_id: UUID,
    error_code: str,
    error_message: str,
) -> None:
    with session_factory() as db:
        fail_analytics_stage(
            db=db,
            stage_run_id=stage_run_id,
            error_code=error_code,
            error_message=error_message,
        )
        db.commit()


def execute_decision_analytics_stage(
    *,
    session_factory: SessionFactory,
    stage_run_id: UUID,
) -> AnalysisResult:
    with session_factory() as db:
        claim = claim_analytics_stage(
            db=db,
            stage_run_id=stage_run_id,
        )
        db.commit()

    try:
        analytics_result = build_decision_analytics_result(
            finance_stage_run_id=claim.finance_stage_run_id,
            finance_bundle=claim.finance_bundle,
        )

    except (
        DecisionAnalyticsComparisonError,
        DecisionSensitivityError,
    ) as exc:
        _mark_analytics_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="DECISION_ANALYTICS_CALCULATION_ERROR",
            error_message=(
                "Decision Analytics failed deterministic calculation validation."
            ),
        )
        raise AnalyticsExecutionError(
            "Decision Analytics calculation failed"
        ) from exc

    except Exception as exc:
        _mark_analytics_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="DECISION_ANALYTICS_EXECUTION_ERROR",
            error_message=(
                "Decision Analytics execution raised "
                f"{type(exc).__name__}."
            ),
        )
        raise AnalyticsExecutionError(
            "Decision Analytics execution failed"
        ) from exc

    try:
        with session_factory() as db:
            persisted_result = complete_analytics_stage(
                db=db,
                stage_run_id=stage_run_id,
                result_data=analytics_result,
            )
            db.commit()
            return persisted_result

    except AnalyticsStageResultValidationError as exc:
        _mark_analytics_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="INVALID_DECISION_ANALYTICS_RESULT",
            error_message=(
                "Decision Analytics returned an invalid structured result."
            ),
        )
        raise AnalyticsExecutionError(
            "Decision Analytics returned an invalid result"
        ) from exc
