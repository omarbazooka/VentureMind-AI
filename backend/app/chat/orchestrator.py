from app.chat.handlers import (
    HandlerResult,
    handle_general_chat,
)
from app.schemas.turn import (
    ExecutionMode,
    Intent,
    TurnUnderstanding,
)
from app.chat.context import WorkingContext


class TurnOrchestratorError(RuntimeError):
    pass


class UnsupportedExecutionModeError(
    TurnOrchestratorError
):
    pass


class UnsupportedIntentError(
    TurnOrchestratorError
):
    pass

class TurnOrchestrator:
    def execute(
        self,
        turn: TurnUnderstanding,
        context: WorkingContext,
    ) -> HandlerResult:
        if turn.execution_mode != ExecutionMode.SINGLE:
            raise UnsupportedExecutionModeError(
                "Only SINGLE execution is supported in v1"
            )

        request = turn.sub_requests[0]

        if request.intent == Intent.GENERAL_CHAT:
            return handle_general_chat(request, context,)

        raise UnsupportedIntentError(
            f"Intent is not implemented yet: "
            f"{request.intent.value}"
        )
        