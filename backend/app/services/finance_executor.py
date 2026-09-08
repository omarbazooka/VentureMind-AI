from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.finance.input_options import (
    build_finance_input_request,
)
from app.finance.scenarios import (
    FinanceScenarioError,
    calculate_financial_scenarios,
)
from app.models.analysis_result import AnalysisResult
from app.schemas.finance import (
    FinanceReadinessResult,
    FinanceReadinessStatus,
    FinancialScenarioInputs,
)
from app.schemas.finance_ai import (
    FinanceAssumptionBuilderContext,
    FinancialAssumptionDraftBundle,
)
from app.schemas.finance_runtime import (
    FinanceExecutionOutcome,
    FinanceExecutionStatus,
)
from app.services.finance_grounding import (
    FinanceGroundingError,
    finalize_financial_assumptions,
)
from app.services.finance_readiness import (
    CRITICAL_FINANCE_INPUTS,
    evaluate_finance_readiness,
)
from app.services.finance_run_inputs import (
    FinanceRunInputGroundingError,
    apply_answered_finance_inputs,
)
from app.services.finance_stage import (
    FinanceStageResultValidationError,
    claim_finance_stage,
    complete_finance_stage,
    fail_finance_stage,
    load_answered_finance_inputs,
    pause_finance_for_user_input,
)


SessionFactory = Callable[
    [],
    Session,
]

FinanceAssumptionRunner = Callable[
    [FinanceAssumptionBuilderContext],
    FinancialAssumptionDraftBundle,
]


class FinanceExecutionError(RuntimeError):
    pass


def _mark_finance_failed(
    *,
    session_factory: SessionFactory,
    stage_run_id: UUID,
    error_code: str,
    error_message: str,
) -> None:
    with session_factory() as db:
        fail_finance_stage(
            db=db,
            stage_run_id=stage_run_id,
            error_code=error_code,
            error_message=error_message,
        )
        db.commit()


def _evaluate_readiness(
    inputs: FinancialScenarioInputs,
) -> tuple[
    FinanceReadinessResult,
    FinanceReadinessResult,
    FinanceReadinessResult,
]:
    return (
        evaluate_finance_readiness(inputs.base),
        evaluate_finance_readiness(inputs.upside),
        evaluate_finance_readiness(inputs.downside),
    )


def _first_missing_base_input(
    readiness: FinanceReadinessResult,
):
    missing = set(
        readiness.missing_critical_inputs
    )

    for input_name in CRITICAL_FINANCE_INPUTS:
        if input_name in missing:
            return input_name

    return None


def _has_incompatible_inputs(
    readiness_results: tuple[
        FinanceReadinessResult,
        FinanceReadinessResult,
        FinanceReadinessResult,
    ],
) -> bool:
    return any(
        readiness.status
        == FinanceReadinessStatus.INCOMPATIBLE_INPUTS
        for readiness in readiness_results
    )


def _secondary_scenarios_are_incomplete(
    readiness_results: tuple[
        FinanceReadinessResult,
        FinanceReadinessResult,
        FinanceReadinessResult,
    ],
) -> bool:
    return any(
        readiness.missing_critical_inputs
        for readiness in readiness_results[1:]
    )


def execute_finance_stage(
    *,
    session_factory: SessionFactory,
    stage_run_id: UUID,
    assumption_runner: FinanceAssumptionRunner,
) -> FinanceExecutionOutcome:
    with session_factory() as db:
        claim = claim_finance_stage(
            db=db,
            stage_run_id=stage_run_id,
        )
        db.commit()

    try:
        drafts = assumption_runner(
            claim.assumption_context
        )

        inputs = finalize_financial_assumptions(
            drafts=drafts,
            context=claim.assumption_context,
        )

        with session_factory() as db:
            answered_inputs = (
                load_answered_finance_inputs(
                    db=db,
                    stage_run_id=stage_run_id,
                )
            )

        inputs = apply_answered_finance_inputs(
            inputs=inputs,
            run_inputs=answered_inputs,
            analysis_run_id=claim.analysis_run_id,
            stage_run_id=stage_run_id,
        )

        readiness_results = _evaluate_readiness(
            inputs
        )

        if _has_incompatible_inputs(
            readiness_results
        ):
            _mark_finance_failed(
                session_factory=session_factory,
                stage_run_id=stage_run_id,
                error_code=(
                    "INCOMPATIBLE_FINANCE_INPUTS"
                ),
                error_message=(
                    "Finance inputs have incompatible "
                    "currency or unit metadata."
                ),
            )
            raise FinanceExecutionError(
                "Finance inputs are incompatible"
            )

        missing_input = _first_missing_base_input(
            readiness_results[0]
        )

        if missing_input is not None:
            request = build_finance_input_request(
                input_name=missing_input,
                assumptions=inputs.base,
                context=claim.assumption_context,
            )

            with session_factory() as db:
                run_input = (
                    pause_finance_for_user_input(
                        db=db,
                        stage_run_id=stage_run_id,
                        request=request,
                    )
                )
                db.commit()

            return FinanceExecutionOutcome(
                stage_run_id=stage_run_id,
                analysis_run_id=(
                    claim.analysis_run_id
                ),
                status=(
                    FinanceExecutionStatus
                    .PAUSED_FOR_USER
                ),
                run_input_id=run_input.id,
                request=request,
            )

        if _secondary_scenarios_are_incomplete(
            readiness_results
        ):
            _mark_finance_failed(
                session_factory=session_factory,
                stage_run_id=stage_run_id,
                error_code=(
                    "INCOMPLETE_FINANCE_SCENARIOS"
                ),
                error_message=(
                    "Upside or downside assumptions are "
                    "missing critical inputs even though "
                    "the base case is complete."
                ),
            )
            raise FinanceExecutionError(
                "Finance scenario assumptions are incomplete"
            )

        result_bundle = (
            calculate_financial_scenarios(
                inputs
            )
        )

        with session_factory() as db:
            persisted_result: AnalysisResult = (
                complete_finance_stage(
                    db=db,
                    stage_run_id=stage_run_id,
                    result_data=result_bundle,
                )
            )
            db.commit()

        return FinanceExecutionOutcome(
            stage_run_id=stage_run_id,
            analysis_run_id=claim.analysis_run_id,
            status=FinanceExecutionStatus.COMPLETED,
            result_id=persisted_result.id,
        )

    except FinanceExecutionError:
        raise

    except FinanceGroundingError as exc:
        _mark_finance_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="INVALID_FINANCE_GROUNDING",
            error_message=(
                "Finance assumptions failed "
                "deterministic grounding."
            ),
        )
        raise FinanceExecutionError(
            "Finance grounding verification failed"
        ) from exc

    except FinanceRunInputGroundingError as exc:
        _mark_finance_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="INVALID_FINANCE_USER_INPUT",
            error_message=(
                "Persisted Finance user input "
                "failed deterministic grounding."
            ),
        )
        raise FinanceExecutionError(
            "Finance user input grounding failed"
        ) from exc

    except FinanceScenarioError as exc:
        _mark_finance_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="FINANCE_SCENARIO_ERROR",
            error_message=(
                "Finance scenario calculation "
                "failed deterministic validation."
            ),
        )
        raise FinanceExecutionError(
            "Finance scenario calculation failed"
        ) from exc

    except FinanceStageResultValidationError as exc:
        _mark_finance_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="INVALID_FINANCE_RESULT",
            error_message=(
                "Finance returned an invalid "
                "structured result."
            ),
        )
        raise FinanceExecutionError(
            "Finance returned an invalid result"
        ) from exc

    except Exception as exc:
        _mark_finance_failed(
            session_factory=session_factory,
            stage_run_id=stage_run_id,
            error_code="FINANCE_EXECUTION_ERROR",
            error_message=(
                "Finance execution raised "
                f"{type(exc).__name__}."
            ),
        )
        raise FinanceExecutionError(
            "Finance execution failed"
        ) from exc
