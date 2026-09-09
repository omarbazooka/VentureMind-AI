from uuid import UUID

from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.models.analysis_run import AnalysisRun
from app.models.analysis_stage_run import AnalysisStageRun
from app.schemas.analysis import (
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.analytics import DecisionAnalyticsResult
from app.schemas.risk import RiskAnalysis


CHAT_READABLE_ANALYSIS_STAGES = frozenset(
    {
        AnalysisStage.DECISION_ANALYTICS,
        AnalysisStage.RISK,
    }
)


class ChatAnalysisContextError(RuntimeError):
    pass


class ChatAnalysisContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idea_id: UUID
    analysis_run_id: UUID
    decision_analytics: DecisionAnalyticsResult | None = None
    risk_analysis: RiskAnalysis | None = None


def _load_latest_completed_result(
    *,
    db: Session,
    analysis_run_id: UUID,
    stage: AnalysisStage,
) -> AnalysisResult | None:
    statement = (
        select(AnalysisResult)
        .join(
            AnalysisStageRun,
            AnalysisStageRun.id == AnalysisResult.stage_run_id,
        )
        .where(
            AnalysisResult.analysis_run_id == analysis_run_id,
            AnalysisResult.stage == stage.value,
            AnalysisStageRun.stage == stage.value,
            AnalysisStageRun.status == AnalysisStageStatus.COMPLETED.value,
        )
        .order_by(
            AnalysisStageRun.attempt.desc(),
            AnalysisResult.created_at.desc(),
        )
        .limit(1)
    )
    return db.scalar(statement)


def load_chat_analysis_context(
    *,
    db: Session,
    idea_id: UUID,
    analysis_run_id: UUID,
    stages: set[AnalysisStage] | frozenset[AnalysisStage] | None = None,
) -> ChatAnalysisContext:
    requested_stages = (
        set(stages)
        if stages is not None
        else set(CHAT_READABLE_ANALYSIS_STAGES)
    )

    unsupported = (
        requested_stages
        - CHAT_READABLE_ANALYSIS_STAGES
    )
    if unsupported:
        raise ValueError(
            "Chat analysis context only supports Decision Analytics and Risk: "
            f"{sorted(stage.value for stage in unsupported)}"
        )

    analysis_run = db.get(
        AnalysisRun,
        analysis_run_id,
    )
    if analysis_run is None:
        raise ChatAnalysisContextError(
            "AnalysisRun was not found"
        )

    if analysis_run.idea_id != idea_id:
        raise ChatAnalysisContextError(
            "AnalysisRun does not belong to the requested idea"
        )

    decision_analytics = None
    risk_analysis = None

    if AnalysisStage.DECISION_ANALYTICS in requested_stages:
        analytics_result = _load_latest_completed_result(
            db=db,
            analysis_run_id=analysis_run_id,
            stage=AnalysisStage.DECISION_ANALYTICS,
        )
        if analytics_result is not None:
            try:
                decision_analytics = (
                    DecisionAnalyticsResult.model_validate(
                        analytics_result.result_data
                    )
                )
            except ValidationError as exc:
                raise ChatAnalysisContextError(
                    "Persisted Decision Analytics result is invalid"
                ) from exc

    if AnalysisStage.RISK in requested_stages:
        risk_result = _load_latest_completed_result(
            db=db,
            analysis_run_id=analysis_run_id,
            stage=AnalysisStage.RISK,
        )
        if risk_result is not None:
            try:
                risk_analysis = RiskAnalysis.model_validate(
                    risk_result.result_data
                )
            except ValidationError as exc:
                raise ChatAnalysisContextError(
                    "Persisted Risk result is invalid"
                ) from exc

    return ChatAnalysisContext(
        idea_id=idea_id,
        analysis_run_id=analysis_run_id,
        decision_analytics=decision_analytics,
        risk_analysis=risk_analysis,
    )
