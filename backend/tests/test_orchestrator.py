from uuid import uuid4

import pytest

from app.chat.context import WorkingContext
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


def make_context() -> WorkingContext:
    return WorkingContext(
        idea_id=uuid4(),
        idea_title="Trainer Marketplace",
        idea_state="COLLECTING_INFORMATION",
        current_user_message="Hello",
        profile_version=1,
        profile_readiness="NOT_READY",
        profile_data={},
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

    context = make_context()

    result = TurnOrchestrator().execute(
        turn,
        context,
    )

    assert result.response_text
    assert "Trainer Marketplace" in result.response_text


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

    context = make_context()

    with pytest.raises(UnsupportedIntentError):
        TurnOrchestrator().execute(
            turn,
            context,
        )


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

    context = make_context()

    with pytest.raises(
        UnsupportedExecutionModeError
    ):
        TurnOrchestrator().execute(
            turn,
            context,
        )
