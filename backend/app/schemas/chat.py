from datetime import datetime
from uuid import UUID

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