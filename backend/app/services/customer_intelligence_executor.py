from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.analysis_result import (
    AnalysisResult,
)
from app.research.customer_evidence import (
    CustomerEvidenceVerificationError,
)
from app.schemas.analysis import (
    AnalysisStage,
)
from app.schemas.research import (
    CustomerAnalysis,
    ResearchStageClaim,
)
from app.services.research_stage import (
    ResearchStageResultValidationError,
    claim_research_stage,
    complete_research_stage,
    fail_research_stage,
)


SessionFactory = Callable[
    [],
    Session,
]

CustomerIntelligenceRunner = Callable[
    [ResearchStageClaim],
    CustomerAnalysis,
]


class CustomerIntelligenceExecutionError(
    RuntimeError
):
    pass


def _mark_customer_intelligence_failed(
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


def execute_customer_intelligence_stage(
    *,
    session_factory: SessionFactory,
    stage_run_id: UUID,
    runner: CustomerIntelligenceRunner,
) -> AnalysisResult:
    with session_factory() as db:
        claim = claim_research_stage(
            db=db,
            stage_run_id=stage_run_id,
        )

        if (
            claim.stage
            != (
                AnalysisStage
                .CUSTOMER_INTELLIGENCE
            )
        ):
            raise (
                CustomerIntelligenceExecutionError(
                    "Customer intelligence "
                    "executor received a "
                    "non-customer stage"
                )
            )

        db.commit()

    try:
        research_result = runner(
            claim
        )

    except (
        CustomerEvidenceVerificationError
    ) as exc:
        _mark_customer_intelligence_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code=(
                "INVALID_CUSTOMER_"
                "INTELLIGENCE_EVIDENCE"
            ),
            error_message=(
                "Customer intelligence "
                "failed deterministic "
                "evidence verification."
            ),
        )

        raise (
            CustomerIntelligenceExecutionError(
                "Customer intelligence "
                "evidence verification failed"
            )
        ) from exc

    except Exception as exc:
        _mark_customer_intelligence_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code=(
                "CUSTOMER_INTELLIGENCE_"
                "EXECUTION_ERROR"
            ),
            error_message=(
                "Customer intelligence "
                "runner raised "
                f"{type(exc).__name__}."
            ),
        )

        raise (
            CustomerIntelligenceExecutionError(
                "Customer intelligence "
                "execution failed"
            )
        ) from exc

    try:
        with session_factory() as db:
            persisted_result = (
                complete_research_stage(
                    db=db,
                    stage_run_id=(
                        stage_run_id
                    ),
                    result_data=(
                        research_result
                    ),
                )
            )

            db.commit()

            return persisted_result

    except (
        ResearchStageResultValidationError
    ) as exc:
        _mark_customer_intelligence_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code=(
                "INVALID_CUSTOMER_"
                "INTELLIGENCE_RESULT"
            ),
            error_message=(
                "Customer intelligence "
                "returned an invalid "
                "structured result."
            ),
        )

        raise (
            CustomerIntelligenceExecutionError(
                "Customer intelligence "
                "returned an invalid "
                "structured result"
            )
        ) from exc
