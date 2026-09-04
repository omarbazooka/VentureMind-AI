from datetime import datetime
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
    CUSTOMER_INTELLIGENCE =  "CUSTOMER_INTELLIGENCE"
    BUSINESS_STRATEGY = "BUSINESS_STRATEGY"
    FINANCE = "FINANCE"


class AnalysisStageStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


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
