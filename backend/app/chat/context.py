from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.chat_session import ChatSession
from app.models.idea import Idea
from app.models.idea_profile import IdeaProfile
from app.models.message import Message


class WorkingContextError(RuntimeError):
    pass


class WorkingMessage(BaseModel):
    role: str
    content: str


class WorkingContext(BaseModel):
    idea_id: UUID
    idea_title: str
    idea_state: str

    current_user_message: str
    current_message_id: UUID | None = None

    profile_version: int
    profile_readiness: str
    profile_data: dict[str, Any]

    recent_messages: list[WorkingMessage] = Field(
        default_factory=list,
    )


def build_working_context(
    *,
    db: Session,
    idea_id: UUID,
    current_user_message: str,
    current_message_id: UUID | None = None,
    recent_message_limit: int = 10,
) -> WorkingContext:
    cleaned_message = current_user_message.strip()

    if not cleaned_message:
        raise ValueError(
            "current_user_message cannot be empty"
        )

    if not 1 <= recent_message_limit <= 50:
        raise ValueError(
            "recent_message_limit must be between 1 and 50"
        )

    idea = db.get(
        Idea,
        idea_id,
    )

    if idea is None:
        raise WorkingContextError(
            "Idea not found"
        )

    profile_statement = (
        select(IdeaProfile)
        .where(
            IdeaProfile.idea_id == idea_id
        )
        .order_by(
            IdeaProfile.version.desc()
        )
        .limit(1)
    )

    profile = db.scalar(
        profile_statement
    )

    if profile is None:
        raise WorkingContextError(
            "Idea profile not found"
        )

    session_statement = (
        select(ChatSession)
        .where(
            ChatSession.idea_id == idea_id
        )
        .order_by(
            ChatSession.created_at.asc()
        )
        .limit(1)
    )

    chat_session = db.scalar(
        session_statement
    )

    recent_messages: list[WorkingMessage] = []

    if chat_session is not None:
        messages_statement = (
            select(Message)
            .where(
                Message.session_id
                == chat_session.id
            )
        )

        if current_message_id is not None:
            messages_statement = (
                messages_statement.where(
                    Message.id != current_message_id
                )
            )

        messages_statement = (
            messages_statement
            .order_by(
                Message.created_at.desc()
            )
            .limit(recent_message_limit)
        )

        messages = list(
            db.scalars(
                messages_statement
            ).all()
        )

        messages.reverse()

        recent_messages = [
            WorkingMessage(
                role=message.role,
                content=message.content,
            )
            for message in messages
        ]

    return WorkingContext(
        idea_id=idea.id,
        idea_title=idea.title,
        idea_state=idea.state,
        current_user_message=cleaned_message,
        current_message_id=current_message_id,
        profile_version=profile.version,
        profile_readiness=profile.readiness,
        profile_data=profile.profile_data,
        recent_messages=recent_messages,
    )