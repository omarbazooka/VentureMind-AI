import pytest

from app.chat.orchestrator import (
    TurnOrchestrator,
    UnsupportedExecutionModeError,
    UnsupportedIntentError,
)
from app.schemas.turn import (
    ExecutionMode,
    Intent,
    SubRequest,
    TurnUnderstanding,
)


def test_orchestrator_executes_general_chat():
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

    result = TurnOrchestrator().execute(turn)

    assert result.response_text


def test_orchestrator_rejects_unsupported_intent():
    turn = TurnUnderstanding(
        sub_requests=[
            SubRequest(
                id="req_1",
                intent=Intent.START_ANALYSIS,
                confidence=0.95,
            )
        ],
        execution_mode=ExecutionMode.SINGLE,
        overall_confidence=0.95,
        clarification_needed=False,
    )

    with pytest.raises(UnsupportedIntentError):
        TurnOrchestrator().execute(turn)


def test_orchestrator_rejects_non_single_mode():
    turn = TurnUnderstanding(
        sub_requests=[
            SubRequest(
                id="req_1",
                intent=Intent.GENERAL_CHAT,
                confidence=0.95,
            ),
            SubRequest(
                id="req_2",
                intent=Intent.GENERAL_CHAT,
                confidence=0.95,
            ),
        ],
        execution_mode=ExecutionMode.PARALLEL,
        overall_confidence=0.95,
        clarification_needed=False,
    )

    with pytest.raises(
        UnsupportedExecutionModeError
    ):
        TurnOrchestrator().execute(turn)