from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.intake import (
    ClarificationQuestion,
    ProfileConflict,
    ProfileReadinessStatus,
    ProfileUnknownConflict,
)


class ChatMessageCreate(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=10000,
    )


class ChatMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime


class ChatTurnStatus(StrEnum):
    COMPLETED = "COMPLETED"

    CLARIFICATION_REQUIRED = (
        "CLARIFICATION_REQUIRED"
    )

    CONFLICT_REQUIRES_CONFIRMATION = (
        "CONFLICT_REQUIRES_CONFIRMATION"
    )

    READY_FOR_ANALYSIS = (
        "READY_FOR_ANALYSIS"
    )


class ChatTurnResponse(BaseModel):
    status: ChatTurnStatus

    user_message: ChatMessageResponse

    assistant_message: ChatMessageResponse

    clarification: (
        ClarificationQuestion
        | None
    ) = None

    profile_version: int | None = Field(
        default=None,
        ge=1,
    )

    profile_readiness: (
        ProfileReadinessStatus
        | None
    ) = None

    conflicts: list[
        ProfileConflict
    ] = Field(
        default_factory=list,
    )

    unknown_conflicts: list[
        ProfileUnknownConflict
    ] = Field(
        default_factory=list,
    )