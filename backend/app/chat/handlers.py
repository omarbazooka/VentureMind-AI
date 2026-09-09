from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.chat.context import WorkingContext
from app.chat.intake_handler import (
    IntakeHandler,
)
from app.schemas.chat import (
    ChatTurnStatus,
)
from app.schemas.intake import (
    ClarificationQuestion,
    IntakeHandlerStatus,
    ProfileConflict,
    ProfileReadinessStatus,
    ProfileUnknownConflict,
)
from app.schemas.turn import (
    Intent,
    SubRequest,
)


class HandlerResult(BaseModel):
    response_text: str

    status: ChatTurnStatus = (
        ChatTurnStatus.COMPLETED
    )

    clarification: (
        ClarificationQuestion
        | None
    ) = None

    profile_version: int | None = Field(
        default=None,
        ge=1,
    )

    profile_readiness: (
        ProfileReadinessStatus
        | None
    ) = None

    conflicts: list[
        ProfileConflict
    ] = Field(
        default_factory=list,
    )

    unknown_conflicts: list[
        ProfileUnknownConflict
    ] = Field(
        default_factory=list,
    )


def handle_general_chat(
    request: SubRequest,
    context: WorkingContext,
) -> HandlerResult:
    if (
        request.intent
        != Intent.GENERAL_CHAT
    ):
        raise ValueError(
            "General chat handler received "
            "unsupported intent"
        )

    return HandlerResult(
        response_text=(
            f"Hi! I’m ready to help with "
            f"{context.idea_title}."
        )
    )


def handle_intake_request(
    *,
    request: SubRequest,
    context: WorkingContext,
    db: Session,
    intake_handler: IntakeHandler,
) -> HandlerResult:
    if request.intent not in {
        Intent.NEW_IDEA,
        Intent.ANSWER_CLARIFICATION,
    }:
        raise ValueError(
            "Intake handler received "
            "unsupported intent"
        )

    intake_result = (
        intake_handler.handle(
            db=db,
            context=context,
        )
    )

    if (
        intake_result.status
        == (
            IntakeHandlerStatus
            .CLARIFICATION_REQUIRED
        )
    ):
        clarification = (
            intake_result.clarification
        )

        if clarification is None:
            raise RuntimeError(
                "Intake handler requested "
                "clarification without a "
                "clarification question"
            )

        return HandlerResult(
            status=(
                ChatTurnStatus
                .CLARIFICATION_REQUIRED
            ),
            response_text=(
                clarification.question
            ),
            clarification=(
                clarification
            ),
            profile_version=(
                intake_result
                .profile_version
            ),
            profile_readiness=(
                intake_result.readiness
            ),
        )

    if (
        intake_result.status
        == (
            IntakeHandlerStatus
            .READY_FOR_ANALYSIS
        )
    ):
        return HandlerResult(
            status=(
                ChatTurnStatus
                .READY_FOR_ANALYSIS
            ),
            response_text=(
                "Your idea profile now has "
                "enough information to start "
                "analysis. Start Analysis when "
                "you're ready."
            ),
            profile_version=(
                intake_result
                .profile_version
            ),
            profile_readiness=(
                intake_result.readiness
            ),
        )

    if (
        intake_result.status
        == (
            IntakeHandlerStatus
            .CONFLICT_REQUIRES_CONFIRMATION
        )
    ):
        return HandlerResult(
            status=(
                ChatTurnStatus
                .CONFLICT_REQUIRES_CONFIRMATION
            ),
            response_text=(
                "I found information in this "
                "message that conflicts with "
                "the current idea profile. "
                "Please confirm the change "
                "before I update it."
            ),
            profile_version=(
                intake_result
                .profile_version
            ),
            profile_readiness=(
                intake_result.readiness
            ),
            conflicts=(
                intake_result.conflicts
            ),
            unknown_conflicts=(
                intake_result
                .unknown_conflicts
            ),
        )

    raise RuntimeError(
        "Unsupported intake handler status: "
        f"{intake_result.status}"
    )


def handle_report_qa_request(
    *,
    request: SubRequest,
    context: WorkingContext,
    db: Session,
) -> HandlerResult:
    from sqlalchemy import desc, select
    from app.models.report import Report
    from app.schemas.report import StructuredReport
    from app.schemas.report_action import (
        ReportActionRequest,
        ReportActionType,
    )
    from app.services.report_action_handler import handle_report_action

    report_record = db.scalar(
        select(Report)
        .where(Report.idea_id == context.idea_id)
        .order_by(desc(Report.version))
        .limit(1)
    )
    if report_record is None:
        return HandlerResult(
            response_text="No analysis report has been generated yet for this idea. Please run the analysis first."
        )

    structured_report = StructuredReport.model_validate(
        report_record.report_data
    )

    intent_map = {
        Intent.ASK_REPORT_QUESTION: ReportActionType.ASK_VENTUREMIND,
        Intent.EXPLAIN_REPORT_SELECTION: ReportActionType.EXPLAIN,
        Intent.SHOW_EVIDENCE: ReportActionType.SHOW_EVIDENCE,
        Intent.SHOW_SOURCES: ReportActionType.SHOW_SOURCES,
        Intent.EXPLAIN_CALCULATION: ReportActionType.EXPLAIN_CALCULATION,
        Intent.CHALLENGE_CONCLUSION: ReportActionType.CHALLENGE_CONCLUSION,
    }
    action_type = intent_map.get(request.intent, ReportActionType.ASK_VENTUREMIND)
    action_request = ReportActionRequest(
        action=action_type,
        target_section=request.payload.get("target_section"),
        target_metric=request.payload.get("target_metric"),
        question=context.current_user_message,
    )
    action_response = handle_report_action(
        report=structured_report,
        request=action_request,
    )
    return HandlerResult(
        response_text=action_response.content,
        status=ChatTurnStatus.COMPLETED,
    )