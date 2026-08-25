from dataclasses import dataclass
from typing import TypeAlias
from uuid import UUID

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.models.analysis_run import AnalysisRun
from app.models.analysis_stage_run import AnalysisStageRun
from app.research.evidence_gate import (
    DEFAULT_MAX_RESEARCH_ATTEMPTS,
    REQUIRED_RESEARCH_STAGES,
    evaluate_research_evidence_gate,
)
from app.schemas.analysis import (
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.research import (
    CompetitorAnalysis,
    CustomerAnalysis,
    MarketAnalysis,
    ResearchEvidenceGateResult,
    ResearchStageGateInput,
)
from app.services.research_stage import RESEARCH_RESULT_SCHEMAS


ResearchAnalysisResult: TypeAlias = (
    MarketAnalysis
    | CompetitorAnalysis
    | CustomerAnalysis
)


@dataclass(frozen=True)
class ResearchJoinEvaluation:
    analysis_run_id: UUID
    gate: ResearchEvidenceGateResult
    results: dict[AnalysisStage, ResearchAnalysisResult]
    latest_stage_run_ids: dict[AnalysisStage, UUID]
    result_stage_run_ids: dict[AnalysisStage, UUID]


class ResearchJoinError(RuntimeError):
    pass


class ResearchJoinRunNotFoundError(
    ResearchJoinError
):
    pass


class ResearchJoinRunStateError(
    ResearchJoinError
):
    pass


class ResearchJoinNotReadyError(
    ResearchJoinError
):
    pass


class ResearchJoinResultValidationError(
    ResearchJoinError
):
    pass


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
        raise ResearchJoinRunNotFoundError(
            "Analysis run not found"
        )

    if (
        analysis_run.status
        != AnalysisRunStatus.RUNNING.value
    ):
        raise ResearchJoinRunStateError(
            "Research Join requires a RUNNING AnalysisRun"
        )

    return analysis_run


def _load_stage_runs(
    *,
    db: Session,
    analysis_run_id: UUID,
) -> list[AnalysisStageRun]:
    statement = (
        select(AnalysisStageRun)
        .where(
            AnalysisStageRun.analysis_run_id
            == analysis_run_id,
            AnalysisStageRun.stage.in_(
                [
                    stage.value
                    for stage
                    in REQUIRED_RESEARCH_STAGES
                ]
            ),
        )
        .order_by(
            AnalysisStageRun.stage,
            AnalysisStageRun.attempt,
        )
    )

    return list(
        db.scalars(statement).all()
    )


def _group_stage_runs(
    stage_runs: list[AnalysisStageRun],
) -> dict[AnalysisStage, list[AnalysisStageRun]]:
    grouped: dict[
        AnalysisStage,
        list[AnalysisStageRun],
    ] = {
        stage: []
        for stage in REQUIRED_RESEARCH_STAGES
    }

    for stage_run in stage_runs:
        try:
            stage = AnalysisStage(
                stage_run.stage
            )
        except ValueError as exc:
            raise ResearchJoinRunStateError(
                "Research Join found an unknown research stage"
            ) from exc

        if stage in grouped:
            grouped[stage].append(stage_run)

    missing = [
        stage
        for stage, attempts in grouped.items()
        if not attempts
    ]

    if missing:
        raise ResearchJoinNotReadyError(
            "Research Join is missing stage runs for: "
            + ", ".join(
                stage.value
                for stage in missing
            )
        )

    return grouped


def _load_results_by_stage_run_id(
    *,
    db: Session,
    stage_run_ids: list[UUID],
) -> dict[UUID, AnalysisResult]:
    if not stage_run_ids:
        return {}

    statement = (
        select(AnalysisResult)
        .where(
            AnalysisResult.stage_run_id.in_(
                stage_run_ids
            )
        )
    )

    return {
        result.stage_run_id: result
        for result
        in db.scalars(statement).all()
    }


def _validate_persisted_result(
    *,
    stage: AnalysisStage,
    analysis_result: AnalysisResult,
) -> ResearchAnalysisResult:
    schema = RESEARCH_RESULT_SCHEMAS[
        stage
    ]

    try:
        validated = schema.model_validate(
            analysis_result.result_data
        )
    except ValidationError as exc:
        raise ResearchJoinResultValidationError(
            "Research Join found an invalid persisted research result "
            f"for {stage.value}"
        ) from exc

    if not isinstance(
        validated,
        (
            MarketAnalysis,
            CompetitorAnalysis,
            CustomerAnalysis,
        ),
    ):
        raise ResearchJoinResultValidationError(
            "Research Join validated an unexpected research result type"
        )

    return validated


def inspect_research_join(
    *,
    db: Session,
    analysis_run_id: UUID,
    max_attempts: int = DEFAULT_MAX_RESEARCH_ATTEMPTS,
) -> ResearchJoinEvaluation:
    _load_analysis_run(
        db=db,
        analysis_run_id=analysis_run_id,
    )

    grouped = _group_stage_runs(
        _load_stage_runs(
            db=db,
            analysis_run_id=analysis_run_id,
        )
    )

    latest_runs = {
        stage: max(
            attempts,
            key=lambda stage_run: stage_run.attempt,
        )
        for stage, attempts in grouped.items()
    }

    for stage, latest_run in latest_runs.items():
        try:
            status = AnalysisStageStatus(
                latest_run.status
            )
        except ValueError as exc:
            raise ResearchJoinRunStateError(
                "Research Join found an invalid stage status "
                f"for {stage.value}"
            ) from exc

        if status not in {
            AnalysisStageStatus.COMPLETED,
            AnalysisStageStatus.FAILED,
        }:
            raise ResearchJoinNotReadyError(
                "Research Join cannot evaluate while latest stage "
                f"{stage.value} is {status.value}"
            )

    completed_runs = [
        stage_run
        for attempts in grouped.values()
        for stage_run in attempts
        if (
            stage_run.status
            == AnalysisStageStatus.COMPLETED.value
        )
    ]

    results_by_stage_run_id = (
        _load_results_by_stage_run_id(
            db=db,
            stage_run_ids=[
                stage_run.id
                for stage_run in completed_runs
            ],
        )
    )

    validated_results: dict[
        AnalysisStage,
        ResearchAnalysisResult,
    ] = {}
    result_stage_run_ids: dict[
        AnalysisStage,
        UUID,
    ] = {}
    gate_inputs: list[
        ResearchStageGateInput
    ] = []

    for stage in REQUIRED_RESEARCH_STAGES:
        attempts = grouped[stage]
        latest_run = latest_runs[stage]
        latest_status = AnalysisStageStatus(
            latest_run.status
        )

        successful_attempts = [
            stage_run
            for stage_run in attempts
            if (
                stage_run.status
                == AnalysisStageStatus.COMPLETED.value
                and stage_run.id
                in results_by_stage_run_id
            )
        ]

        latest_successful_result = None
        latest_successful_run = None

        if successful_attempts:
            latest_successful_run = max(
                successful_attempts,
                key=lambda stage_run: stage_run.attempt,
            )
            latest_successful_result = (
                _validate_persisted_result(
                    stage=stage,
                    analysis_result=(
                        results_by_stage_run_id[
                            latest_successful_run.id
                        ]
                    ),
                )
            )
            validated_results[stage] = (
                latest_successful_result
            )
            result_stage_run_ids[stage] = (
                latest_successful_run.id
            )

        if latest_status == AnalysisStageStatus.COMPLETED:
            if (
                latest_run.id
                not in results_by_stage_run_id
            ):
                raise ResearchJoinRunStateError(
                    "Completed research stage has no persisted result: "
                    f"{stage.value}"
                )

            if (
                latest_successful_run is None
                or latest_successful_run.id
                != latest_run.id
            ):
                latest_successful_result = (
                    _validate_persisted_result(
                        stage=stage,
                        analysis_result=(
                            results_by_stage_run_id[
                                latest_run.id
                            ]
                        ),
                    )
                )
                validated_results[stage] = (
                    latest_successful_result
                )
                result_stage_run_ids[stage] = (
                    latest_run.id
                )

            gate_inputs.append(
                ResearchStageGateInput(
                    stage=stage,
                    attempt=latest_run.attempt,
                    stage_status=latest_status,
                    evidence_quality=(
                        latest_successful_result
                        .evidence_quality
                    ),
                    limitations=(
                        latest_successful_result
                        .limitations
                    ),
                    error_code=None,
                )
            )
        else:
            gate_inputs.append(
                ResearchStageGateInput(
                    stage=stage,
                    attempt=latest_run.attempt,
                    stage_status=latest_status,
                    evidence_quality=None,
                    limitations=(
                        latest_successful_result.limitations
                        if latest_successful_result
                        is not None
                        else []
                    ),
                    error_code=(
                        latest_run.error_code
                    ),
                )
            )

    gate = evaluate_research_evidence_gate(
        stages=gate_inputs,
        max_attempts=max_attempts,
    )

    return ResearchJoinEvaluation(
        analysis_run_id=analysis_run_id,
        gate=gate,
        results=validated_results,
        latest_stage_run_ids={
            stage: stage_run.id
            for stage, stage_run
            in latest_runs.items()
        },
        result_stage_run_ids=(
            result_stage_run_ids
        ),
    )

@dataclass(frozen=True)
class ScheduledResearchRetry:
    stage: AnalysisStage
    stage_run_id: UUID
    attempt: int


class ResearchJoinStaleEvaluationError(
    ResearchJoinError
):
    pass


def _load_run_for_retry_scheduling(
    *,
    db: Session,
    analysis_run_id: UUID,
) -> AnalysisRun:
    statement = (
        select(AnalysisRun)
        .where(
            AnalysisRun.id == analysis_run_id
        )
        .with_for_update()
    )

    analysis_run = db.scalar(statement)

    if analysis_run is None:
        raise ResearchJoinRunNotFoundError(
            "Analysis run not found"
        )

    if (
        analysis_run.status
        != AnalysisRunStatus.RUNNING.value
    ):
        raise ResearchJoinRunStateError(
            "Research retries require a RUNNING AnalysisRun"
        )

    return analysis_run


def schedule_targeted_retries(
    *,
    db: Session,
    evaluation: ResearchJoinEvaluation,
    max_attempts: int = DEFAULT_MAX_RESEARCH_ATTEMPTS,
) -> list[ScheduledResearchRetry]:
    if max_attempts < 1:
        raise ValueError(
            "max_attempts must be at least 1"
        )

    if not evaluation.gate.retry_stages:
        return []

    _load_run_for_retry_scheduling(
        db=db,
        analysis_run_id=(
            evaluation.analysis_run_id
        ),
    )

    assessment_by_stage = {
        assessment.stage: assessment
        for assessment
        in evaluation.gate.assessments
    }

    scheduled: list[
        ScheduledResearchRetry
    ] = []

    for stage in evaluation.gate.retry_stages:
        assessment = assessment_by_stage[
            stage
        ]

        if not assessment.retry_eligible:
            raise ResearchJoinStaleEvaluationError(
                "Gate requested retry for a stage that is not retry eligible"
            )

        next_attempt = assessment.attempt + 1

        if next_attempt > max_attempts:
            raise ResearchJoinStaleEvaluationError(
                "Gate requested a retry beyond the configured attempt budget"
            )

        existing_statement = (
            select(AnalysisStageRun)
            .where(
                AnalysisStageRun.analysis_run_id
                == evaluation.analysis_run_id,
                AnalysisStageRun.stage
                == stage.value,
                AnalysisStageRun.attempt
                == next_attempt,
            )
        )

        existing_retry = db.scalar(
            existing_statement
        )

        if existing_retry is not None:
            scheduled.append(
                ScheduledResearchRetry(
                    stage=stage,
                    stage_run_id=(
                        existing_retry.id
                    ),
                    attempt=(
                        existing_retry.attempt
                    ),
                )
            )
            continue

        current_statement = (
            select(AnalysisStageRun)
            .where(
                AnalysisStageRun.analysis_run_id
                == evaluation.analysis_run_id,
                AnalysisStageRun.stage
                == stage.value,
            )
            .order_by(
                AnalysisStageRun.attempt.desc()
            )
            .limit(1)
        )

        current_latest = db.scalar(
            current_statement
        )

        if (
            current_latest is None
            or current_latest.attempt
            != assessment.attempt
        ):
            raise ResearchJoinStaleEvaluationError(
                "Research retry evaluation is stale; inspect the join again"
            )

        retry_stage_run = AnalysisStageRun(
            analysis_run_id=(
                evaluation.analysis_run_id
            ),
            stage=stage.value,
            attempt=next_attempt,
            status=(
                AnalysisStageStatus.PENDING.value
            ),
        )

        db.add(
            retry_stage_run
        )
        db.flush()

        scheduled.append(
            ScheduledResearchRetry(
                stage=stage,
                stage_run_id=(
                    retry_stage_run.id
                ),
                attempt=next_attempt,
            )
        )

    return scheduled
