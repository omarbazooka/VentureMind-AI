from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.intake import (
    ProfileField,
    ProfileFieldMetadata,
    ProfileValue,
)


class IdeaProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_data: dict[ProfileField, ProfileValue]


class IdeaProfileResponse(BaseModel):
    idea_id: UUID
    version: int
    readiness: str
    profile_data: dict[str, Any]
    profile_metadata: dict[
        str,
        ProfileFieldMetadata,
    ] = Field(default_factory=dict)
    unknown_fields: list[ProfileField] = Field(
        default_factory=list,
    )
