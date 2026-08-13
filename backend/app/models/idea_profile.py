import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class IdeaProfile(Base):
    __tablename__ = "idea_profiles"

    __table_args__ = (
        UniqueConstraint(
            "idea_id",
            "version",
            name="uq_idea_profiles_idea_id_version",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )

    idea_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ideas.id"),
        nullable=False,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    readiness: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="NOT_READY",
    )

    profile_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )

    profile_metadata: Mapped[
        dict[str, dict[str, Any]]
    ] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )


    unknown_fields: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
    )

    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )