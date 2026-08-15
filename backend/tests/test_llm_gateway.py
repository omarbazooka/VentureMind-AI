import pytest
from pydantic import BaseModel
from unittest.mock import Mock

from app.llm.gateway import (
    LLMGateway,
    LLMGatewayError,
    LLMInvalidOutputError,
)
from app.schemas.turn import (
    ExecutionMode,
    Intent,
    TurnUnderstanding,
)

class ChildWithDefault(BaseModel):
    value_kind: str = "FACT"


class ParentWithDefault(BaseModel):
    children: list[ChildWithDefault]


class FakeInteraction:
    def __init__(self, output_text: str):
        self.output_text = output_text


class FakeInteractions:
    def __init__(
        self,
        output_text: str | None = None,
        error: Exception | None = None,
    ):
        self.output_text = output_text
        self.error = error

    def create(self, **kwargs):
        if self.error is not None:
            raise self.error

        return FakeInteraction(
            self.output_text
        )


class FakeGeminiClient:
    def __init__(
        self,
        output_text: str | None = None,
        error: Exception | None = None,
    ):
        self.interactions = FakeInteractions(
            output_text=output_text,
            error=error,
        )


def test_generate_structured_returns_validated_model():
    client = FakeGeminiClient(
        output_text="""
        {
            "sub_requests": [
                {
                    "id": "req_1",
                    "intent": "GENERAL_CHAT",
                    "payload": {},
                    "confidence": 0.95,
                    "depends_on": []
                }
            ],
            "execution_mode": "SINGLE",
            "overall_confidence": 0.95,
            "clarification_needed": false
        }
        """
    )

    gateway = LLMGateway(client=client)

    result = gateway.generate_structured(
        model="test-model",
        system_prompt="Understand the user turn.",
        user_prompt="Hello",
        response_model=TurnUnderstanding,
    )

    assert isinstance(
        result,
        TurnUnderstanding,
    )

    assert (
        result.execution_mode
        == ExecutionMode.SINGLE
    )

    assert (
        result.sub_requests[0].intent
        == Intent.GENERAL_CHAT
    )


def test_generate_structured_rejects_invalid_output():
    client = FakeGeminiClient(
        output_text="""
        {
            "execution_mode": "INVALID"
        }
        """
    )

    gateway = LLMGateway(client=client)

    with pytest.raises(
        LLMInvalidOutputError
    ):
        gateway.generate_structured(
            model="test-model",
            system_prompt="Understand the user turn.",
            user_prompt="Hello",
            response_model=TurnUnderstanding,
        )


def test_generate_structured_normalizes_provider_error():
    client = FakeGeminiClient(
        error=RuntimeError(
            "provider exploded"
        )
    )

    gateway = LLMGateway(client=client)

    with pytest.raises(
        LLMGatewayError
    ):
        gateway.generate_structured(
            model="test-model",
            system_prompt="Understand the user turn.",
            user_prompt="Hello",
            response_model=TurnUnderstanding,
        )

def test_generate_structured_retries_after_invalid_output():
    client = Mock()

    client.interactions.create.side_effect = [
        FakeInteraction(
            """
            {
                "execution_mode": "INVALID"
            }
            """
        ),
        FakeInteraction(
            """
            {
                "sub_requests": [
                    {
                        "id": "req_1",
                        "intent": "GENERAL_CHAT",
                        "payload": {},
                        "confidence": 0.95,
                        "depends_on": []
                    }
                ],
                "execution_mode": "SINGLE",
                "overall_confidence": 0.95,
                "clarification_needed": false
            }
            """
        ),
    ]

    gateway = LLMGateway(
        client=client
    )

    result = gateway.generate_structured(
        model="test-model",
        system_prompt="Understand the turn.",
        user_prompt="Hello",
        response_model=TurnUnderstanding,
    )

    assert (
        result.execution_mode
        == ExecutionMode.SINGLE
    )

    assert (
        client.interactions.create.call_count
        == 2
    )

def test_generate_structured_removes_nested_schema_defaults():
    client = Mock()

    client.interactions.create.return_value = (
        FakeInteraction(
            """
            {
                "children": [
                    {}
                ]
            }
            """
        )
    )

    gateway = LLMGateway(
        client=client
    )

    result = gateway.generate_structured(
        model="test-model",
        system_prompt="Test.",
        user_prompt="Test.",
        response_model=ParentWithDefault,
    )

    call_kwargs = (
        client
        .interactions
        .create
        .call_args
        .kwargs
    )

    schema = (
        call_kwargs[
            "response_format"
        ][
            "schema"
        ]
    )

    child_schema = (
        schema[
            "$defs"
        ][
            "ChildWithDefault"
        ][
            "properties"
        ][
            "value_kind"
        ]
    )

    assert (
        "default"
        not in child_schema
    )

    assert (
        result.children[0].value_kind
        == "FACT"
    )