from unittest.mock import Mock

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

    result = controller.handle_message(
        "Hello"
    )

    assert (
        result.status
        == ChatTurnStatus.COMPLETED
    )

    assert result.response_text


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

    result = controller.handle_message(
        "Do it."
    )

    assert (
        result.status
        == ChatTurnStatus.CLARIFICATION_REQUIRED
    )

    orchestrator.execute.assert_not_called()