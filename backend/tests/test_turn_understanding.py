from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.chat.context import WorkingContext
from app.chat.turn_understanding import (
    TurnUnderstandingService,
)
from app.llm.gateway import LLMGateway
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


def test_understand_returns_gateway_result():
    expected = TurnUnderstanding(
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

    gateway = Mock(spec=LLMGateway)
    gateway.generate_structured.return_value = expected

    service = TurnUnderstandingService(
        gateway=gateway,
        model="test-model",
    )

    context = make_context()

    result = service.understand(
        "Hello",
        context,
    )

    assert result == expected

    gateway.generate_structured.assert_called_once()

    call = gateway.generate_structured.call_args.kwargs

    assert call["model"] == "test-model"
    assert call["response_model"] is TurnUnderstanding

    assert (
        "CURRENT USER MESSAGE:\nHello"
        in call["user_prompt"]
    )

    assert (
        "Trainer Marketplace"
        in call["user_prompt"]
    )


def test_understand_rejects_blank_message():
    gateway = Mock(spec=LLMGateway)

    service = TurnUnderstandingService(
        gateway=gateway,
        model="test-model",
    )

    context = make_context(
        current_user_message="   "
    )

    with pytest.raises(
        ValueError,
        match="user_message cannot be empty",
    ):
        service.understand(
            "   ",
            context,
        )

    gateway.generate_structured.assert_not_called()
