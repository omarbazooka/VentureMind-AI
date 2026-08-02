from uuid import UUID
from pydantic import BaseModel, Field

class IdeaCreate(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10, max_length=2000)

class IdeaResponse(BaseModel):
    id: UUID
    title: str
    description: str