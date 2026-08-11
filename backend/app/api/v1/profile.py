from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.idea import Idea
from app.models.idea_profile import IdeaProfile
from app.schemas.profile import IdeaProfileResponse, IdeaProfileUpdate


router = APIRouter(
    prefix= "/ideas",
    tags=["profile"]
)

DbSession = Annotated[Session, Depends(get_db)]

@router.get(
    "/{idea_id}/profile",
    response_model=IdeaProfileResponse,
)
def get_profile(
    idea_id: UUID,
    db: DbSession,
) -> IdeaProfileResponse:
    idea = db.get(Idea, idea_id)

    if idea is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="idea nnot found",
        )

    statement = (
        select(IdeaProfile)
        .where(IdeaProfile.idea_id == idea_id)
        .order_by(IdeaProfile.version.desc())
        .limit(1)
    )

    profile = db.scalar(statement)

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Idea profile not found",
        )

    return IdeaProfileResponse(
        idea_id=profile.idea_id,
        version=profile.version,
        readiness=profile.readiness,
        profile_data=profile.profile_data,
    )



# Update without delete the old profile data
@router.patch(
    "/{idea_id}/profile",
    response_model=IdeaProfileResponse,
)
def update_profile(
    idea_id: UUID,
    payload: IdeaProfileUpdate,
    db: DbSession,
) -> IdeaProfileResponse:
    idea = db.get(Idea, idea_id)

    if idea is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Idea not found",
        )

    statement = (
        select(IdeaProfile)
        .where(IdeaProfile.idea_id == idea_id)
        .order_by(IdeaProfile.version.desc())
        .limit(1)
    )

    current_profile = db.scalar(statement)

    if current_profile is None:
        current_data = {}
        next_version = 1
    else:
        current_data = current_profile.profile_data
        next_version = current_profile.version + 1

    # merge current and update in one profile data:
    # current_data = {
    #     "country": "Egypt",
    #     "industry": "Restaurants",
    # }
    # payload.profile_data = {
    #     "budget": 300000,
    # }
    # 
    #
    # {
    # "country": "Egypt",
    # "industry": "Restaurants",
    # "budget": 300000,
    # }

    new_profile_data = {
        **current_data,
        **payload.profile_data,
    }

    new_profile = IdeaProfile(
        idea_id=idea_id,
        version=next_version,
        readiness="NOT_READY",
        profile_data=new_profile_data,
    )

    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)

    return IdeaProfileResponse(
        idea_id=new_profile.idea_id,
        version=new_profile.version,
        readiness=new_profile.readiness,
        profile_data=new_profile.profile_data,
    )