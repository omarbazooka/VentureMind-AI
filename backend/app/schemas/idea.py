from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

class IdeaCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10, max_length=2000)

class IdeaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    description: str
    owner_user_id: UUID | None = None
    state: str = "NEW"
    created_at: datetime | None = None