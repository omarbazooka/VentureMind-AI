from sqlalchemy.orm import Session

from app.chat.context import WorkingContext
from app.chat.handlers import (
    HandlerResult,
    handle_general_chat,
    handle_intake_request,
)
from app.chat.intake_handler import (
    IntakeHandler,
)
from app.schemas.turn import (
    ExecutionMode,
    Intent,
    TurnUnderstanding,
)


class TurnOrchestratorError(
    RuntimeError
):
    pass


class UnsupportedExecutionModeError(
    TurnOrchestratorError
):
    pass


class UnsupportedIntentError(
    TurnOrchestratorError
):
    pass


class MissingDatabaseSessionError(
    TurnOrchestratorError
):
    pass


class TurnOrchestrator:
    def __init__(
        self,
        intake_handler: (
            IntakeHandler
            | None
        ) = None,
    ) -> None:
        self._intake_handler = (
            intake_handler
            or IntakeHandler()
        )

    def execute(
        self,
        turn: TurnUnderstanding,
        context: WorkingContext,
        db: Session | None = None,
    ) -> HandlerResult:
        if (
            turn.execution_mode
            != ExecutionMode.SINGLE
        ):
            raise (
                UnsupportedExecutionModeError(
                    "Only SINGLE execution is "
                    "supported in v1"
                )
            )

        request = (
            turn.sub_requests[0]
        )

        if (
            request.intent
            == Intent.GENERAL_CHAT
        ):
            return handle_general_chat(
                request,
                context,
            )

        if request.intent in {
            Intent.NEW_IDEA,
            Intent.ANSWER_CLARIFICATION,
        }:
            if db is None:
                raise (
                    MissingDatabaseSessionError(
                        "Intake execution requires "
                        "a database session"
                    )
                )

            return handle_intake_request(
                request=request,
                context=context,
                db=db,
                intake_handler=(
                    self._intake_handler
                ),
            )

        raise UnsupportedIntentError(
            "Intent is not implemented yet: "
            f"{request.intent.value}"
        )