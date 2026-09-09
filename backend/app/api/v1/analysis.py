from typing import Annotated, Any
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.report import Report
from app.schemas.analysis import (
    AnalysisRunCreateResponse,
)
from app.schemas.report import StructuredReport
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


@router.get(
    "/{idea_id}/report/latest",
    response_model=StructuredReport,
)
def get_latest_report(
    idea_id: UUID,
    db: DbSession,
) -> StructuredReport:
    report = db.scalar(
        select(Report)
        .where(Report.idea_id == idea_id)
        .order_by(desc(Report.version))
        .limit(1)
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found for this idea",
        )
    return StructuredReport.model_validate(report.report_data)


@router.get(
    "/{idea_id}/reports",
)
def list_reports(
    idea_id: UUID,
    db: DbSession,
) -> list[dict[str, Any]]:
    reports = db.scalars(
        select(Report)
        .where(Report.idea_id == idea_id)
        .order_by(desc(Report.version))
    ).all()
    return [
        {
            "id": str(r.id),
            "idea_id": str(r.idea_id),
            "analysis_run_id": str(r.analysis_run_id),
            "version": r.version,
            "created_at": r.created_at,
        }
        for r in reports
    ]


@router.get(
    "/{idea_id}/reports/{version}",
    response_model=StructuredReport,
)
def get_report_version(
    idea_id: UUID,
    version: int,
    db: DbSession,
) -> StructuredReport:
    report = db.scalar(
        select(Report).where(
            Report.idea_id == idea_id,
            Report.version == version,
        )
    )
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report version {version} not found for this idea",
        )
    return StructuredReport.model_validate(report.report_data)

