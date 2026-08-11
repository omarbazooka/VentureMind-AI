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
from app.chat.context import build_working_context
from app.chat.controller import ChatController
from app.chat.orchestrator import TurnOrchestratorError
from app.llm.gateway import LLMGatewayError

from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageResponse,
    ChatTurnResponse,
)
router = APIRouter(
    prefix="/ideas",
    tags=["chat"],
)

DbSession = Annotated[Session, Depends(get_db)]

def get_chat_controller() -> ChatController:
    return ChatController()


ChatControllerDep = Annotated[
    ChatController,
    Depends(get_chat_controller),
]

@router.post(
    "/{idea_id}/messages",
    response_model=ChatTurnResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_message(
    idea_id: UUID,
    payload: ChatMessageCreate,
    db: DbSession,
    controller: ChatControllerDep,
) -> ChatTurnResponse:
    idea = db.get(
        Idea,
        idea_id,
    )

    if idea is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Idea not found",
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

    if chat_session is None:
        chat_session = ChatSession(
            idea_id=idea_id,
        )

        db.add(chat_session)
        db.flush()

    user_message = Message(
        session_id=chat_session.id,
        role="user",
        content=payload.content,
    )

    db.add(user_message)

    db.commit()
    db.refresh(user_message)

    context = build_working_context(
        db=db,
        idea_id=idea_id,
        current_user_message=user_message.content,
        current_message_id=user_message.id,
    )

    try:
        turn_result = controller.handle_message(
            user_message.content,
            context,
        )

    except LLMGatewayError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service failed to process the message",
        ) from exc

    except TurnOrchestratorError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    assistant_message = Message(
        session_id=chat_session.id,
        role="assistant",
        content=turn_result.response_text,
    )

    db.add(assistant_message)

    db.commit()
    db.refresh(assistant_message)

    return ChatTurnResponse(
        status=turn_result.status,
        user_message=ChatMessageResponse(
            id=user_message.id,
            role=user_message.role,
            content=user_message.content,
            created_at=user_message.created_at,
        ),
        assistant_message=ChatMessageResponse(
            id=assistant_message.id,
            role=assistant_message.role,
            content=assistant_message.content,
            created_at=assistant_message.created_at,
        ),
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
