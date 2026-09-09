from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.intake import ProfileReadinessStatus


class AnalysisRunStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED_FOR_USER = "PAUSED_FOR_USER"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AnalysisStage(StrEnum):
    MARKET_RESEARCH = "MARKET_RESEARCH"
    COMPETITOR_INTELLIGENCE = "COMPETITOR_INTELLIGENCE"
    CUSTOMER_INTELLIGENCE = "CUSTOMER_INTELLIGENCE"
    BUSINESS_STRATEGY = "BUSINESS_STRATEGY"
    FINANCE = "FINANCE"
    DECISION_ANALYTICS = "DECISION_ANALYTICS"
    RISK = "RISK"
    INDEPENDENT_VALIDATION = "INDEPENDENT_VALIDATION"
    INVESTMENT_COMMITTEE = "INVESTMENT_COMMITTEE"


class AnalysisStageStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED_FOR_USER = "PAUSED_FOR_USER"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AnalysisRunInputStatus(StrEnum):
    PENDING = "PENDING"
    ANSWERED = "ANSWERED"
    CANCELLED = "CANCELLED"


class AnalysisProfileSnapshot(BaseModel):
    readiness: ProfileReadinessStatus
    profile_data: dict[str, Any]
    profile_metadata: dict[
        str,
        dict[str, Any],
    ] = Field(default_factory=dict)
    unknown_fields: list[str] = Field(
        default_factory=list,
    )

class AnalysisRunCreateResponse(BaseModel):
    run_id: UUID
    idea_id: UUID
    profile_id: UUID
    profile_version: int = Field(ge=1)
    status: AnalysisRunStatus
    created_at: datetime


class StageProgressItem(BaseModel):
    stage: str
    attempt: int
    status: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_code: str | None = None
    error_message: str | None = None


class PendingInputSummary(BaseModel):
    input_id: UUID
    stage_run_id: UUID
    input_name: str
    question: str
    options: list[dict[str, Any]] = Field(default_factory=list)
    allow_custom: bool = True
    currency: str | None = None
    unit_label: str | None = None
    period: str | None = None


class AnalysisProgressResponse(BaseModel):
    idea_id: UUID
    analysis_run_id: UUID | None = None
    run_status: str
    current_stage: str | None = None
    completed_stages: list[str] = Field(default_factory=list)
    stage_runs: list[StageProgressItem] = Field(default_factory=list)
    pending_input: PendingInputSummary | None = None
    has_report: bool = False
    report_version: int | None = None
    error_code: str | None = None
    error_message: str | None = None


class AnswerInputRequest(BaseModel):
    value: Decimal | None = None
    choice: str | None = None
    text: str | None = None
    currency: str | None = None
    unit_label: str | None = None
    period: str | None = None
    source_message_id: UUID | None = None


class AnswerInputResponse(BaseModel):
    input_id: UUID
    status: str
    analysis_run_status: str
    message: str

