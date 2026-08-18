from datetime import datetime, timezone
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis_run import AnalysisRun
from app.models.analysis_stage_run import AnalysisStageRun
from app.schemas.analysis import (
    AnalysisProfileSnapshot,
    AnalysisRunStatus,
    AnalysisStage,
    AnalysisStageStatus,
)
from app.schemas.intake import ProfileReadinessStatus
from app.services.intake_profile import (
    evaluate_profile_readiness,
)


INITIAL_RESEARCH_STAGES = (
    AnalysisStage.MARKET_RESEARCH,
    AnalysisStage.COMPETITOR_INTELLIGENCE,
    AnalysisStage.CUSTOMER_INTELLIGENCE,
)


class BusinessAnalysisFlowError(RuntimeError):
    pass


class BusinessAnalysisRunNotFoundError(
    BusinessAnalysisFlowError
):
    pass


class BusinessAnalysisRunStateError(
    BusinessAnalysisFlowError
):
    pass


class BusinessAnalysisSnapshotError(
    BusinessAnalysisFlowError
):
    pass


class BusinessAnalysisFlow:
    def _load_run_for_update(
        self,
        *,
        db: Session,
        run_id: UUID,
    ) -> AnalysisRun:
        statement = (
            select(AnalysisRun)
            .where(
                AnalysisRun.id == run_id
            )
            .with_for_update()
        )

        analysis_run = db.scalar(statement)

        if analysis_run is None:
            raise BusinessAnalysisRunNotFoundError(
                "Analysis run not found"
            )

        return analysis_run

    def _validate_snapshot(
        self,
        analysis_run: AnalysisRun,
    ) -> AnalysisProfileSnapshot:
        try:
            snapshot = (
                AnalysisProfileSnapshot
                .model_validate(
                    analysis_run.profile_snapshot
                )
            )
        except ValidationError as exc:
            raise BusinessAnalysisSnapshotError(
                "Analysis run contains an invalid "
                "profile snapshot"
            ) from exc

        readiness_result = (
            evaluate_profile_readiness(
                profile_data=(
                    snapshot.profile_data
                ),
                profile_metadata=(
                    snapshot.profile_metadata
                ),
                unknown_fields=(
                    snapshot.unknown_fields
                ),
            )
        )

        if (
            snapshot.readiness
            != (
                ProfileReadinessStatus
                .READY_FOR_ANALYSIS
            )
            or readiness_result.readiness
            != (
                ProfileReadinessStatus
                .READY_FOR_ANALYSIS
            )
        ):
            raise BusinessAnalysisSnapshotError(
                "Analysis run snapshot is not "
                "ready for analysis"
            )

        return snapshot

    def _ensure_initial_stage_runs(
        self,
        *,
        db: Session,
        analysis_run: AnalysisRun,
    ) -> None:
        statement = (
            select(AnalysisStageRun)
            .where(
                AnalysisStageRun.analysis_run_id
                == analysis_run.id,
                AnalysisStageRun.attempt == 1,
            )
        )

        existing_stage_runs = list(
            db.scalars(statement).all()
        )

        existing_stages = {
            stage_run.stage
            for stage_run
            in existing_stage_runs
        }

        for stage in INITIAL_RESEARCH_STAGES:
            if stage.value in existing_stages:
                continue

            db.add(
                AnalysisStageRun(
                    analysis_run_id=(
                        analysis_run.id
                    ),
                    stage=stage.value,
                    attempt=1,
                    status=(
                        AnalysisStageStatus
                        .PENDING
                        .value
                    ),
                )
            )

    def initialize(
        self,
        *,
        db: Session,
        run_id: UUID,
    ) -> AnalysisRun:
        analysis_run = (
            self._load_run_for_update(
                db=db,
                run_id=run_id,
            )
        )

        allowed_statuses = {
            AnalysisRunStatus.QUEUED.value,
            AnalysisRunStatus.RUNNING.value,
        }

        if (
            analysis_run.status
            not in allowed_statuses
        ):
            raise BusinessAnalysisRunStateError(
                "Analysis run cannot be "
                "initialized from status "
                f"{analysis_run.status}"
            )

        self._validate_snapshot(
            analysis_run
        )

        self._ensure_initial_stage_runs(
            db=db,
            analysis_run=analysis_run,
        )

        if (
            analysis_run.status
            == AnalysisRunStatus.QUEUED.value
        ):
            analysis_run.status = (
                AnalysisRunStatus.RUNNING.value
            )

        if analysis_run.started_at is None:
            analysis_run.started_at = (
                datetime.now(timezone.utc)
            )

        analysis_run.error_code = None
        analysis_run.error_message = None

        db.flush()

        return analysis_run