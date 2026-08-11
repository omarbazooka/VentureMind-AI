from enum import StrEnum

from pydantic import BaseModel

from app.chat.orchestrator import TurnOrchestrator
from app.chat.turn_policy import (
    TurnPolicyAction,
    evaluate_turn,
)
from app.chat.turn_understanding import (
    TurnUnderstandingService,
)
from app.schemas.turn import TurnUnderstanding
from app.chat.context import WorkingContext
from app.schemas.chat import ChatTurnStatus

class ChatTurnResult(BaseModel):
    status: ChatTurnStatus
    response_text: str
    turn_understanding: TurnUnderstanding

class ChatController:
    def __init__(
        self,
        turn_understanding_service: TurnUnderstandingService | None = None,
        orchestrator : TurnOrchestrator | None = None,
    ) -> None:
        self._turn_understanding_service = (
            turn_understanding_service
            or
            TurnUnderstandingService()
        )

        self._orchestrator = (
            orchestrator
            or
            TurnOrchestrator()
        )

    def handle_message(
        self,
        user_message: str,
        context: WorkingContext,
    ) -> ChatTurnResult:
        turn = (
            self._turn_understanding_service
            .understand(user_message, context,)
        )

        policy_decision = evaluate_turn(
            turn
        )

        if(policy_decision.action == TurnPolicyAction.CLARIFY):
            return ChatTurnResult(
                status = (ChatTurnStatus.CLARIFICATION_REQUIRED),
                response_text = (
                    "Could you clarify what you want me "
                    "to do?"
                ),
                turn_understanding = turn,
            )

        handler_result = self._orchestrator.execute(
            turn, context,
        )

        return ChatTurnResult(
            status = ChatTurnStatus.COMPLETED,
            response_text = handler_result.response_text,
            turn_understanding = turn,
        )