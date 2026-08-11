from datetime import datetime
from uuid import UUID
from enum import StrEnum

from pydantic import BaseModel, Field


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
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"


class ChatTurnResponse(BaseModel):
    status: ChatTurnStatus
    user_message: ChatMessageResponse
    assistant_message: ChatMessageResponse

