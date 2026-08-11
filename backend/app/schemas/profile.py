from typing import Any
from uuid import UUID

from pydantic import BaseModel

class IdeaProfileUpdate(BaseModel):
    profile_data: dict[str, Any]

class IdeaProfileResponse(BaseModel):
    idea_id: UUID
    version: int
    readiness: str
    profile_data: dict[str, Any]