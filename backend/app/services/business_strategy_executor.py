from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.analysis_result import (
    AnalysisResult,
)
from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.strategy import (
    BusinessStrategyAnalysis,
    StrategyStageClaim,
)
from app.services.strategy_grounding import (
    StrategyGroundingError,
)
from app.services.strategy_stage import (
    StrategyStageResultValidationError,
    claim_strategy_stage,
    complete_strategy_stage,
    fail_strategy_stage,
)


SessionFactory = Callable[
    [],
    Session,
]

BusinessStrategyRunner = Callable[
    [StrategyStageClaim],
    BusinessStrategyAnalysis,
]


class BusinessStrategyExecutionError(
    RuntimeError
):
    pass


def _mark_business_strategy_failed(
    *,
    session_factory: SessionFactory,
    stage_run_id: UUID,
    error_code: str,
    error_message: str,
) -> None:
    with session_factory() as db:
        fail_strategy_stage(
            db=db,
            stage_run_id=stage_run_id,
            error_code=error_code,
            error_message=error_message,
        )

        db.commit()


def execute_business_strategy_stage(
    *,
    session_factory: SessionFactory,
    stage_run_id: UUID,
    runner: BusinessStrategyRunner,
) -> AnalysisResult:
    with session_factory() as db:
        claim = claim_strategy_stage(
            db=db,
            stage_run_id=stage_run_id,
        )

        if (
            claim.stage
            != AnalysisStage.BUSINESS_STRATEGY
        ):
            raise BusinessStrategyExecutionError(
                "Business Strategy executor "
                "received a non-strategy stage"
            )

        db.commit()

    try:
        strategy_result = runner(
            claim
        )

    except StrategyGroundingError as exc:
        _mark_business_strategy_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code=(
                "INVALID_BUSINESS_STRATEGY_GROUNDING"
            ),
            error_message=(
                "Business Strategy failed "
                "deterministic grounding."
            ),
        )

        raise BusinessStrategyExecutionError(
            "Business Strategy grounding "
            "verification failed"
        ) from exc

    except Exception as exc:
        _mark_business_strategy_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code=(
                "BUSINESS_STRATEGY_EXECUTION_ERROR"
            ),
            error_message=(
                "Business Strategy runner raised "
                f"{type(exc).__name__}."
            ),
        )

        raise BusinessStrategyExecutionError(
            "Business Strategy execution failed"
        ) from exc

    try:
        with session_factory() as db:
            persisted_result = (
                complete_strategy_stage(
                    db=db,
                    stage_run_id=stage_run_id,
                    result_data=strategy_result,
                )
            )

            db.commit()

            return persisted_result

    except (
        StrategyStageResultValidationError
    ) as exc:
        _mark_business_strategy_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code=(
                "INVALID_BUSINESS_STRATEGY_RESULT"
            ),
            error_message=(
                "Business Strategy returned "
                "an invalid structured or "
                "ungrounded result."
            ),
        )

        raise BusinessStrategyExecutionError(
            "Business Strategy returned "
            "an invalid result"
        ) from exc