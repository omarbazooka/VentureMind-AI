from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chat.context import WorkingContext
from app.models.idea_profile import IdeaProfile
from app.schemas.intake import (
    IntakeHandlerResult,
    IntakeHandlerStatus,
    ProfileReadinessStatus,
)
from app.services.intake_clarification import (
    IntakeClarificationService,
)
from app.services.intake_extraction import (
    IntakeExtractionService,
)
from app.services.intake_profile import (
    evaluate_profile_readiness,
    persist_profile_merge_plan,
    plan_profile_merge,
    select_next_clarification_target,
)


class IntakeHandlerError(
    RuntimeError
):
    pass


class IntakeProfileNotFoundError(
    IntakeHandlerError
):
    pass


class IntakeHandler:
    def __init__(
        self,
        extraction_service: (
            IntakeExtractionService
            | None
        ) = None,
        clarification_service: (
            IntakeClarificationService
            | None
        ) = None,
    ) -> None:
        self._extraction_service = (
            extraction_service
            or IntakeExtractionService()
        )

        self._clarification_service = (
            clarification_service
            or IntakeClarificationService()
        )

    def _get_latest_profile(
        self,
        *,
        db: Session,
        context: WorkingContext,
    ) -> IdeaProfile:
        statement = (
            select(IdeaProfile)
            .where(
                IdeaProfile.idea_id
                == context.idea_id
            )
            .order_by(
                IdeaProfile.version.desc()
            )
            .limit(1)
        )

        profile = db.scalar(
            statement
        )

        if profile is None:
            raise IntakeProfileNotFoundError(
                "Idea profile not found"
            )

        return profile

    def handle(
        self,
        *,
        db: Session,
        context: WorkingContext,
    ) -> IntakeHandlerResult:
        current_profile = (
            self._get_latest_profile(
                db=db,
                context=context,
            )
        )

        extraction = (
            self._extraction_service
            .extract(
                context
            )
        )

        merge_plan = (
            plan_profile_merge(
                current_data=(
                    current_profile
                    .profile_data
                ),
                updates=(
                    extraction.updates
                ),
                current_unknown_fields=(
                    current_profile
                    .unknown_fields
                    or []
                ),
                declared_unknown_fields=(
                    extraction
                    .unknown_fields
                ),
            )
        )

        if (
            merge_plan.conflicts
            or merge_plan.unknown_conflicts
        ):
            current_readiness = (
                evaluate_profile_readiness(
                    profile_data=(
                        current_profile
                        .profile_data
                    ),
                    profile_metadata=(
                        current_profile
                        .profile_metadata
                        or {}
                    ),
                    unknown_fields=(
                        current_profile
                        .unknown_fields
                        or []
                    ),
                )
            )

            return IntakeHandlerResult(
                status=(
                    IntakeHandlerStatus
                    .CONFLICT_REQUIRES_CONFIRMATION
                ),
                profile_version=(
                    current_profile.version
                ),
                readiness=(
                    current_readiness
                    .readiness
                ),
                conflicts=(
                    merge_plan.conflicts
                ),
                unknown_conflicts=(
                    merge_plan
                    .unknown_conflicts
                ),
            )

        profile = (
            persist_profile_merge_plan(
                db=db,
                idea_id=(
                    context.idea_id
                ),
                current_profile=(
                    current_profile
                ),
                merge_plan=(
                    merge_plan
                ),
                source_message_id=(
                    context
                    .current_message_id
                ),
            )
        )

        readiness_result = (
            evaluate_profile_readiness(
                profile_data=(
                    profile.profile_data
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
            == (
                ProfileReadinessStatus
                .READY_FOR_ANALYSIS
            )
        ):
            return IntakeHandlerResult(
                status=(
                    IntakeHandlerStatus
                    .READY_FOR_ANALYSIS
                ),
                profile_version=(
                    profile.version
                ),
                readiness=(
                    readiness_result
                    .readiness
                ),
            )

        target = (
            select_next_clarification_target(
                readiness_result=(
                    readiness_result
                ),
                profile_data=(
                    profile.profile_data
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

        if target is None:
            raise IntakeHandlerError(
                "Profile is NOT_READY but "
                "no clarification target "
                "was found"
            )

        clarification = (
            self._clarification_service
            .compose(
                target=target,
                profile_data=(
                    profile.profile_data
                ),
                unknown_fields=(
                    profile.unknown_fields
                    or []
                ),
                latest_user_message=(
                    context
                    .current_user_message
                ),
            )
        )

        return IntakeHandlerResult(
            status=(
                IntakeHandlerStatus
                .CLARIFICATION_REQUIRED
            ),
            profile_version=(
                profile.version
            ),
            readiness=(
                readiness_result
                .readiness
            ),
            clarification=(
                clarification
            ),
        )