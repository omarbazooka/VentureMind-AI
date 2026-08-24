from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.schemas.analysis import AnalysisStage
from app.schemas.research import (
    MarketAnalysis,
    ResearchStageClaim,
)
from app.services.research_stage import (
    ResearchStageResultValidationError,
    claim_research_stage,
    complete_research_stage,
    fail_research_stage,
)


SessionFactory = Callable[[], Session]

MarketResearchRunner = Callable[
    [ResearchStageClaim],
    MarketAnalysis,
]


class MarketResearchExecutionError(
    RuntimeError
):
    pass

def _mark_market_research_failed(
    *,
    session_factory: SessionFactory,
    stage_run_id: UUID,
    error_code: str,
    error_message: str,
) -> None:
    with session_factory() as db:
        fail_research_stage(
            db=db,
            stage_run_id=stage_run_id,
            error_code=error_code,
            error_message=error_message,
        )

        db.commit()

def execute_market_research_stage(
    *,
    session_factory: SessionFactory,
    stage_run_id: UUID,
    runner: MarketResearchRunner,
) -> AnalysisResult:
    with session_factory() as db:
        claim = claim_research_stage(
            db=db,
            stage_run_id=stage_run_id,
        )

        if (
            claim.stage
            != AnalysisStage.MARKET_RESEARCH
        ):
            raise MarketResearchExecutionError(
                "Market research executor "
                "received a non-market stage"
            )

        db.commit()

    try:
        research_result = runner(
            claim
        )

    except Exception as exc:
        _mark_market_research_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code=(
                "MARKET_RESEARCH_EXECUTION_ERROR"
            ),
            error_message=(
                "Market research runner raised "
                f"{type(exc).__name__}."
            ),
        )

        raise MarketResearchExecutionError(
            "Market research execution failed"
        ) from exc

    try:
        with session_factory() as db:
            persisted_result = (
                complete_research_stage(
                    db=db,
                    stage_run_id=stage_run_id,
                    result_data=research_result,
                )
            )

            db.commit()

            return persisted_result

    except ResearchStageResultValidationError as exc:
        _mark_market_research_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code=(
                "INVALID_MARKET_RESEARCH_RESULT"
            ),
            error_message=(
                "Market research returned an "
                "invalid structured result."
            ),
        )

        raise MarketResearchExecutionError(
            "Market research returned an "
            "invalid structured result"
        ) from exc