from unittest.mock import Mock
from uuid import uuid4

from app.chat.context import WorkingContext
from app.chat.controller import (
    ChatController,
    ChatTurnStatus,
)
from app.chat.orchestrator import TurnOrchestrator
from app.chat.turn_understanding import (
    TurnUnderstandingService,
)
from app.schemas.turn import (
    ExecutionMode,
    Intent,
    SubRequest,
    TurnUnderstanding,
)


def make_context(
    current_user_message: str = "Hello",
) -> WorkingContext:
    return WorkingContext(
        idea_id=uuid4(),
        idea_title="Trainer Marketplace",
        idea_state="COLLECTING_INFORMATION",
        current_user_message=current_user_message,
        profile_version=1,
        profile_readiness="NOT_READY",
        profile_data={},
    )


def test_controller_executes_accepted_single_turn():
    turn = TurnUnderstanding(
        sub_requests=[
            SubRequest(
                id="req_1",
                intent=Intent.GENERAL_CHAT,
                confidence=0.95,
            )
        ],
        execution_mode=ExecutionMode.SINGLE,
        overall_confidence=0.95,
        clarification_needed=False,
    )

    service = Mock(
        spec=TurnUnderstandingService
    )
    service.understand.return_value = turn

    controller = ChatController(
        turn_understanding_service=service,
        orchestrator=TurnOrchestrator(),
    )

    context = make_context()

    result = controller.handle_message(
        "Hello",
        context,
    )

    assert (
        result.status
        == ChatTurnStatus.COMPLETED
    )

    assert result.response_text

    service.understand.assert_called_once_with(
        "Hello",
        context,
    )


def test_controller_stops_for_clarification():
    turn = TurnUnderstanding(
        sub_requests=[
            SubRequest(
                id="req_1",
                intent=Intent.GENERAL_CHAT,
                confidence=0.2,
            )
        ],
        execution_mode=ExecutionMode.SINGLE,
        overall_confidence=0.2,
        clarification_needed=True,
    )

    service = Mock(
        spec=TurnUnderstandingService
    )
    service.understand.return_value = turn

    orchestrator = Mock(
        spec=TurnOrchestrator
    )

    controller = ChatController(
        turn_understanding_service=service,
        orchestrator=orchestrator,
    )

    context = make_context(
        current_user_message="Do it."
    )

    result = controller.handle_message(
        "Do it.",
        context,
    )

    assert (
        result.status
        == ChatTurnStatus.CLARIFICATION_REQUIRED
    )

    service.understand.assert_called_once_with(
        "Do it.",
        context,
    )

    orchestrator.execute.assert_not_called()
