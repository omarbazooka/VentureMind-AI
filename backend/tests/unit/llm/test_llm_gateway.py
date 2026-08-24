import pytest
from pydantic import BaseModel, Field
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


class ChildWithProviderUnsupportedKeywords(BaseModel):
    value_kind: str = "FACT"
    label: str = Field(
        min_length=1,
        max_length=20,
    )


class ParentWithProviderUnsupportedKeywords(BaseModel):
    children: list[
        ChildWithProviderUnsupportedKeywords
    ]


class FakeResponse:
    def __init__(
        self,
        text: str | None,
    ) -> None:
        self.text = text


class FakeModels:
    def __init__(
        self,
        text: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.text = text
        self.error = error
        self.calls: list[dict] = []

    def generate_content(
        self,
        **kwargs,
    ) -> FakeResponse:
        self.calls.append(kwargs)

        if self.error is not None:
            raise self.error

        return FakeResponse(
            self.text
        )


class FakeGeminiClient:
    def __init__(
        self,
        text: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.models = FakeModels(
            text=text,
            error=error,
        )


VALID_TURN_JSON = """
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


def test_generate_structured_returns_validated_model():
    client = FakeGeminiClient(
        text=VALID_TURN_JSON
    )

    gateway = LLMGateway(
        client=client
    )

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

    call = client.models.calls[0]

    assert (
        call["config"]["response_mime_type"]
        == "application/json"
    )
    assert (
        "response_json_schema"
        in call["config"]
    )


def test_generate_structured_rejects_invalid_output():
    client = FakeGeminiClient(
        text="""
        {
            "execution_mode": "INVALID"
        }
        """
    )

    gateway = LLMGateway(
        client=client
    )

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

    gateway = LLMGateway(
        client=client
    )

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

    client.models.generate_content.side_effect = [
        FakeResponse(
            """
            {
                "execution_mode": "INVALID"
            }
            """
        ),
        FakeResponse(
            VALID_TURN_JSON
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
        client.models
        .generate_content
        .call_count
        == 2
    )

    retry_config = (
        client.models
        .generate_content
        .call_args_list[1]
        .kwargs["config"]
    )

    assert (
        "RETRY INSTRUCTION"
        in retry_config[
            "system_instruction"
        ]
    )


def test_generate_structured_sanitizes_provider_schema():
    client = Mock()

    client.models.generate_content.return_value = (
        FakeResponse(
            """
            {
                "children": [
                    {
                        "label": "valid"
                    }
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
        response_model=(
            ParentWithProviderUnsupportedKeywords
        ),
    )

    call_kwargs = (
        client.models
        .generate_content
        .call_args
        .kwargs
    )

    schema = (
        call_kwargs["config"][
            "response_json_schema"
        ]
    )

    child_schema = (
        schema["$defs"][
            "ChildWithProviderUnsupportedKeywords"
        ]["properties"]
    )

    value_kind_schema = (
        child_schema["value_kind"]
    )
    label_schema = (
        child_schema["label"]
    )

    assert (
        "default"
        not in value_kind_schema
    )
    assert (
        "minLength"
        not in label_schema
    )
    assert (
        "maxLength"
        not in label_schema
    )

    assert (
        result.children[0].value_kind
        == "FACT"
    )
    assert (
        result.children[0].label
        == "valid"
    )
