from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser, get_current_user, get_optional_user
from app.core.database import get_db
from app.models.chat_session import ChatSession
from app.models.idea import Idea
from app.models.idea_profile import IdeaProfile
from app.schemas.idea import IdeaCreate, IdeaResponse

router = APIRouter(prefix="/ideas", tags=["ideas"])

DbSession = Annotated[Session, Depends(get_db)]
OptionalUser = Annotated[AuthenticatedUser | None, Depends(get_optional_user)]
CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def check_idea_ownership(idea: Idea, user: AuthenticatedUser | None) -> None:
    """Enforce ownership access control.

    If idea has an owner, user must match owner.
    Unowned ideas (e.g. initial demo/test ideas) are publicly accessible.
    """
    if idea.owner_user_id is not None:
        if user is None or user.user_id != idea.owner_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: you do not have permission to access this idea",
            )


@router.get(
    "",
    response_model=list[IdeaResponse],
)
def list_ideas(
    db: DbSession,
    user: OptionalUser = None,
) -> list[IdeaResponse]:
    """List ideas accessible to the user (owned ideas + public demo ideas)."""
    stmt = select(Idea).order_by(desc(Idea.created_at))
    if user:
        stmt = stmt.where(
            or_(
                Idea.owner_user_id == user.user_id,
                Idea.owner_user_id.is_(None),
            )
        )
    else:
        stmt = stmt.where(Idea.owner_user_id.is_(None))

    ideas = list(db.scalars(stmt).all())
    return [
        IdeaResponse(
            id=i.id,
            title=i.title,
            description=i.raw_initial_idea,
            owner_user_id=i.owner_user_id,
            state=i.state,
            created_at=i.created_at,
        )
        for i in ideas
    ]


@router.post(
    "",
    response_model=IdeaResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_idea(
    payload: IdeaCreate,
    db: DbSession,
    user: OptionalUser = None,
) -> IdeaResponse:
    owner_id = user.user_id if user else None

    idea = Idea(
        title=payload.title,
        raw_initial_idea=payload.description,
        owner_user_id=owner_id,
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
        owner_user_id=idea.owner_user_id,
        state=idea.state,
        created_at=idea.created_at,
    )


@router.get(
    "/{idea_id}",
    response_model=IdeaResponse,
)
def get_idea(
    idea_id: UUID,
    db: DbSession,
    user: OptionalUser = None,
) -> IdeaResponse:
    idea = db.get(Idea, idea_id)
    if idea is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Idea not found",
        )

    check_idea_ownership(idea, user)

    return IdeaResponse(
        id=idea.id,
        title=idea.title,
        description=idea.raw_initial_idea,
        owner_user_id=idea.owner_user_id,
        state=idea.state,
        created_at=idea.created_at,
    )
