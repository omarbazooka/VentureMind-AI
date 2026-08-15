from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.idea import Idea
from app.models.idea_profile import IdeaProfile
from app.schemas.intake import (
    IntakeProvenance,
    ProfileFieldUpdate,
)
from app.schemas.profile import (
    IdeaProfileResponse,
    IdeaProfileUpdate,
)
from app.services.intake_profile import (
    ProfileValueValidationError,
    persist_profile_merge_plan,
    plan_profile_merge,
)


router = APIRouter(
    prefix="/ideas",
    tags=["profile"],
)

DbSession = Annotated[
    Session,
    Depends(get_db),
]


def _get_latest_profile(
    *,
    db: Session,
    idea_id: UUID,
) -> IdeaProfile | None:
    statement = (
        select(IdeaProfile)
        .where(IdeaProfile.idea_id == idea_id)
        .order_by(IdeaProfile.version.desc())
        .limit(1)
    )

    return db.scalar(statement)


def _to_response(
    profile: IdeaProfile,
) -> IdeaProfileResponse:
    return IdeaProfileResponse(
        idea_id=profile.idea_id,
        version=profile.version,
        readiness=profile.readiness,
        profile_data=profile.profile_data,
        profile_metadata=profile.profile_metadata or {},
        unknown_fields=profile.unknown_fields or [],
    )


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
            detail="Idea not found",
        )

    profile = _get_latest_profile(
        db=db,
        idea_id=idea_id,
    )

    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Idea profile not found",
        )

    return _to_response(profile)


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

    current_profile = _get_latest_profile(
        db=db,
        idea_id=idea_id,
    )

    if current_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Idea profile not found",
        )

    updates = [
        ProfileFieldUpdate(
            field=field,
            value=value,
            provenance=IntakeProvenance.USER,
            confidence=1.0,
        )
        for field, value in payload.profile_data.items()
    ]

    try:
        merge_plan = plan_profile_merge(
            current_data=(
                current_profile.profile_data
            ),
            updates=updates,
            current_unknown_fields=(
                current_profile.unknown_fields
                or []
            ),
        )
    except ProfileValueValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if merge_plan.conflicts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "Profile update conflicts with the current profile"
                ),
                "conflicts": [
                    conflict.model_dump(mode="json")
                    for conflict in merge_plan.conflicts
                ],
            },
        )

    profile = persist_profile_merge_plan(
        db=db,
        idea_id=idea_id,
        current_profile=current_profile,
        merge_plan=merge_plan,
    )

    if profile is not current_profile:
        db.commit()
        db.refresh(profile)

    return _to_response(profile)
