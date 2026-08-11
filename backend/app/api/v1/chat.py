from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.chat_session import ChatSession
from app.models.idea import Idea
from app.models.message import Message
from app.schemas.chat import ChatMessageCreate, ChatMessageResponse

router = APIRouter(
    prefix="/ideas",
    tags=["chat"],
)

DbSession = Annotated[Session, Depends(get_db)]

@router.post(
    "/{idea_id}/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    idea_id: UUID,
    payload: ChatMessageCreate,
    db: DbSession,
) -> ChatMessageResponse:
    idea = db.get(Idea, idea_id)

    if idea is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Idea not found",
        )
    statement = (
        select(ChatSession)
        .where(ChatSession.idea_id == idea_id)
        .order_by(ChatSession.created_at.asc())
        .limit(1)
    )

    chat_session = db.scalar(statement)

    if chat_session is None:
        chat_session = ChatSession(
            idea_id=idea_id,
        )
        db.add(chat_session)
        db.flush()

    message = Message(
        session_id=chat_session.id,
        role="user",
        content=payload.content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    return ChatMessageResponse(
        id=message.id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
    )

@router.get(
    "/{idea_id}/messages",
    response_model=list[ChatMessageResponse],
)
def get_messages(
    idea_id: UUID,
    db: DbSession,
) -> list[ChatMessageResponse]:
    idea = db.get(Idea, idea_id)
    
    if idea is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Idea not found",
        )

    session_statement = (
        select(ChatSession)
        .where(ChatSession.idea_id == idea_id)
        .order_by(ChatSession.created_at.asc())
        .limit(1)
    )
    # need one object
    chat_session = db.scalar(session_statement)

    if chat_session is None:
        return []

    messages_statement = (
        select(Message)
        .where(Message.session_id == chat_session.id)
        .order_by(Message.created_at.asc())
    )
    # need more objects
    messages = db.scalars(messages_statement).all()

    return [
        ChatMessageResponse(
            id=message.id,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
        )
        for message in messages
    ]
