from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.analysis import AnalysisRunStatus, AnalysisStage


class ReanalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_stage: AnalysisStage | None = Field(
        default=None,
        description="Explicit stage from which to restart downstream analysis. If omitted, inferred from profile changes.",
    )
    profile_updates: dict[str, Any] | None = Field(
        default=None,
        description="Updated fields to apply to a new IdeaProfile version before re-analysis.",
    )
    reason: str | None = Field(
        default=None,
        max_length=1000,
        description="Reason or rationale for triggering re-analysis.",
    )


class ReanalysisResponse(BaseModel):
    idea_id: UUID
    new_analysis_run_id: UUID
    new_profile_version: int
    invalidated_stages: list[AnalysisStage]
    reused_stages: list[AnalysisStage]
    reused_result_ids: dict[str, str]
    status: AnalysisRunStatus


class MetricComparisonItem(BaseModel):
    metric_name: str
    v1_value: Any | None = None
    v2_value: Any | None = None
    delta: Any | None = None
    direction: str | None = None  # "UP", "DOWN", "UNCHANGED", "NEW", "REMOVED"


class ReportComparisonResponse(BaseModel):
    idea_id: UUID
    v1_report_id: UUID
    v1_version: int
    v2_report_id: UUID
    v2_version: int
    v1_analysis_run_id: UUID
    v2_analysis_run_id: UUID
    decision_comparison: dict[str, Any]  # {"v1_decision": "NO_GO", "v2_decision": "GO", "changed": True}
    financial_comparison: list[MetricComparisonItem]
    risk_comparison: dict[str, Any]  # {"v1_high_risks": 2, "v2_high_risks": 0, "net_risk_change": -2}
    lineage_comparison: dict[str, Any]  # {"reused_stages": [...], "re_executed_stages": [...]}
    executive_takeaway: str
