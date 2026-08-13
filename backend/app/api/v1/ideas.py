from uuid import uuid4
from app.schemas.idea import IdeaCreate, IdeaResponse
from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.idea import Idea
from app.models.chat_session import ChatSession
from app.models.idea_profile import IdeaProfile

router = APIRouter(prefix="/ideas", tags=["ideas"])

DbSession = Annotated[Session, Depends(get_db)]

@router.post(
    "",
    response_model=IdeaResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_idea(
    payload: IdeaCreate,
    db: DbSession,
) -> IdeaResponse:
    idea = Idea(
        title=payload.title,
        raw_initial_idea=payload.description,
    )

    db.add(idea)
    db.flush()

    chat_session = ChatSession(
        idea_id=idea.id,
    )

    
    idea_profile = IdeaProfile(
        idea_id=idea.id,
        version=1,
        readiness="NOT_READY",
        profile_data={},
        profile_metadata={},
        unknown_fields=[],
    )

    db.add(chat_session)
    db.add(idea_profile)

    db.commit()
    db.refresh(idea)

    return IdeaResponse(
        id=idea.id,
        title=idea.title,
        description=idea.raw_initial_idea,
    )

@router.get(
    "/{idea_id}",
        response_model=IdeaResponse,
)
def get_idea(
    idea_id: UUID,
    db: DbSession
    ) -> IdeaResponse:
    idea = db.get(Idea, idea_id)

    if idea is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Idea not found",
        )

    return IdeaResponse(
        id=idea.id,
        title=idea.title,
        description=idea.raw_initial_idea,
        state=idea.state,
        created_at=idea.created_at,
        updated_at=idea.updated_at,
    )
