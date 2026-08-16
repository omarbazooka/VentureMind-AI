from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.chat.context import WorkingContext
from app.chat.orchestrator import TurnOrchestrator
from app.chat.turn_policy import (
    TurnPolicyAction,
    evaluate_turn,
)
from app.chat.turn_understanding import (
    TurnUnderstandingService,
)
from app.schemas.chat import ChatTurnStatus
from app.schemas.intake import (
    ClarificationQuestion,
    ProfileConflict,
    ProfileReadinessStatus,
    ProfileUnknownConflict,
)
from app.schemas.turn import TurnUnderstanding


class ChatTurnResult(BaseModel):
    status: ChatTurnStatus
    response_text: str
    turn_understanding: TurnUnderstanding

    clarification: ClarificationQuestion | None = None

    profile_version: int | None = Field(
        default=None,
        ge=1,
    )

    profile_readiness: (
        ProfileReadinessStatus
        | None
    ) = None

    conflicts: list[ProfileConflict] = Field(
        default_factory=list,
    )

    unknown_conflicts: list[
        ProfileUnknownConflict
    ] = Field(
        default_factory=list,
    )


class ChatController:
    def __init__(
        self,
        turn_understanding_service: (
            TurnUnderstandingService
            | None
        ) = None,
        orchestrator: TurnOrchestrator | None = None,
    ) -> None:
        self._turn_understanding_service = (
            turn_understanding_service
            or TurnUnderstandingService()
        )

        self._orchestrator = (
            orchestrator
            or TurnOrchestrator()
        )

    def handle_message(
        self,
        user_message: str,
        context: WorkingContext,
        db: Session | None = None,
    ) -> ChatTurnResult:
        turn = (
            self._turn_understanding_service
            .understand(
                user_message,
                context,
            )
        )

        policy_decision = evaluate_turn(
            turn
        )

        if (
            policy_decision.action
            == TurnPolicyAction.CLARIFY
        ):
            return ChatTurnResult(
                status=(
                    ChatTurnStatus
                    .CLARIFICATION_REQUIRED
                ),
                response_text=(
                    "Could you clarify what you "
                    "want me to do?"
                ),
                turn_understanding=turn,
            )

        handler_result = (
            self._orchestrator.execute(
                turn,
                context,
                db=db,
            )
        )

        return ChatTurnResult(
            status=handler_result.status,
            response_text=(
                handler_result.response_text
            ),
            turn_understanding=turn,
            clarification=(
                handler_result.clarification
            ),
            profile_version=(
                handler_result.profile_version
            ),
            profile_readiness=(
                handler_result.profile_readiness
            ),
            conflicts=handler_result.conflicts,
            unknown_conflicts=(
                handler_result.unknown_conflicts
            ),
        )
