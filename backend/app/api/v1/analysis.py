from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.analysis import (
    AnalysisRunCreateResponse,
)
from app.services.analysis_run import (
    AnalysisIdeaNotFoundError,
    AnalysisProfileNotFoundError,
    AnalysisProfileNotReadyError,
    AnalysisRunAlreadyActiveError,
    start_analysis_run,
)


router = APIRouter(
    prefix="/ideas",
    tags=["analysis"],
)

DbSession = Annotated[
    Session,
    Depends(get_db),
]


@router.post(
    "/{idea_id}/analysis",
    response_model=AnalysisRunCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_analysis(
    idea_id: UUID,
    db: DbSession,
) -> AnalysisRunCreateResponse:
    try:
        analysis_run = start_analysis_run(
            db=db,
            idea_id=idea_id,
        )
    except AnalysisIdeaNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Idea not found",
        ) from exc
    except AnalysisProfileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Idea profile not found",
        ) from exc
    except AnalysisProfileNotReadyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "Idea profile is not ready "
                    "for analysis"
                ),
                **(
                    exc.readiness_result
                    .model_dump(mode="json")
                ),
            },
        ) from exc
    except AnalysisRunAlreadyActiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "An analysis run is already "
                    "active for this idea"
                ),
                "run_id": str(
                    exc.analysis_run.id
                ),
                "status": (
                    exc.analysis_run.status
                ),
            },
        ) from exc

    db.commit()
    db.refresh(analysis_run)

    return AnalysisRunCreateResponse(
        run_id=analysis_run.id,
        idea_id=analysis_run.idea_id,
        profile_id=analysis_run.profile_id,
        profile_version=(
            analysis_run.profile_version
        ),
        status=analysis_run.status,
        created_at=analysis_run.created_at,
    )
