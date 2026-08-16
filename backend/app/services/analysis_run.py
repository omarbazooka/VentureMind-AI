from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis_run import AnalysisRun
from app.models.idea import Idea
from app.models.idea_profile import IdeaProfile
from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisRunStatus,
)
from app.schemas.intake import (
    ProfileReadinessResult,
    ProfileReadinessStatus,
)
from app.services.intake_profile import (
    evaluate_profile_readiness,
)


ACTIVE_ANALYSIS_RUN_STATUSES = {
    AnalysisRunStatus.QUEUED,
    AnalysisRunStatus.RUNNING,
    AnalysisRunStatus.PAUSED_FOR_USER,
    AnalysisRunStatus.VALIDATING,
}


class AnalysisStartError(RuntimeError):
    pass


class AnalysisIdeaNotFoundError(
    AnalysisStartError
):
    pass


class AnalysisProfileNotFoundError(
    AnalysisStartError
):
    pass


class AnalysisProfileNotReadyError(
    AnalysisStartError
):
    def __init__(
        self,
        readiness_result: ProfileReadinessResult,
    ) -> None:
        self.readiness_result = readiness_result
        super().__init__(
            "Idea profile is not ready for analysis"
        )


class AnalysisRunAlreadyActiveError(
    AnalysisStartError
):
    def __init__(
        self,
        analysis_run: AnalysisRun,
    ) -> None:
        self.analysis_run = analysis_run
        super().__init__(
            "An analysis run is already active "
            "for this idea"
        )


def _get_latest_profile(
    *,
    db: Session,
    idea_id: UUID,
) -> IdeaProfile | None:
    statement = (
        select(IdeaProfile)
        .where(
            IdeaProfile.idea_id == idea_id
        )
        .order_by(
            IdeaProfile.version.desc()
        )
        .limit(1)
    )

    return db.scalar(statement)


def _get_active_analysis_run(
    *,
    db: Session,
    idea_id: UUID,
) -> AnalysisRun | None:
    active_status_values = [
        status.value
        for status in ACTIVE_ANALYSIS_RUN_STATUSES
    ]

    statement = (
        select(AnalysisRun)
        .where(
            AnalysisRun.idea_id == idea_id,
            AnalysisRun.status.in_(
                active_status_values
            ),
        )
        .order_by(
            AnalysisRun.created_at.desc()
        )
        .limit(1)
    )

    return db.scalar(statement)


def start_analysis_run(
    *,
    db: Session,
    idea_id: UUID,
) -> AnalysisRun:
    idea = db.get(
        Idea,
        idea_id,
    )

    if idea is None:
        raise AnalysisIdeaNotFoundError(
            "Idea not found"
        )

    active_run = _get_active_analysis_run(
        db=db,
        idea_id=idea_id,
    )

    if active_run is not None:
        raise AnalysisRunAlreadyActiveError(
            active_run
        )

    profile = _get_latest_profile(
        db=db,
        idea_id=idea_id,
    )

    if profile is None:
        raise AnalysisProfileNotFoundError(
            "Idea profile not found"
        )

    readiness_result = (
        evaluate_profile_readiness(
            profile_data=(
                profile.profile_data
                or {}
            ),
            profile_metadata=(
                profile.profile_metadata
                or {}
            ),
            unknown_fields=(
                profile.unknown_fields
                or []
            ),
        )
    )

    if (
        readiness_result.readiness
        != (
            ProfileReadinessStatus
            .READY_FOR_ANALYSIS
        )
    ):
        raise AnalysisProfileNotReadyError(
            readiness_result
        )

    snapshot = AnalysisProfileSnapshot(
        readiness=readiness_result.readiness,
        profile_data=dict(
            profile.profile_data
            or {}
        ),
        profile_metadata=dict(
            profile.profile_metadata
            or {}
        ),
        unknown_fields=list(
            profile.unknown_fields
            or []
        ),
    )

    analysis_run = AnalysisRun(
        idea_id=idea_id,
        profile_id=profile.id,
        profile_version=profile.version,
        profile_snapshot=(
            snapshot.model_dump(
                mode="json"
            )
        ),
        status=(
            AnalysisRunStatus
            .QUEUED
            .value
        ),
    )

    db.add(
        analysis_run
    )
    db.flush()

    return analysis_run
