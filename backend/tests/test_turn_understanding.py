from unittest.mock import Mock

import pytest

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

    result = service.understand("Hello")

    assert result == expected

    gateway.generate_structured.assert_called_once()

    call = gateway.generate_structured.call_args.kwargs

    assert call["model"] == "test-model"
    assert call["user_prompt"] == "Hello"
    assert call["response_model"] is TurnUnderstanding


def test_understand_rejects_blank_message():
    gateway = Mock(spec=LLMGateway)

    service = TurnUnderstandingService(
        gateway=gateway,
        model="test-model",
    )

    with pytest.raises(
        ValueError,
        match="user_message cannot be empty",
    ):
        service.understand("   ")

    gateway.generate_structured.assert_not_called()