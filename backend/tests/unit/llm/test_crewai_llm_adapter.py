from unittest.mock import Mock

import pytest
from pydantic import BaseModel

from app.llm.crewai_adapter import (
    CrewAILLMAdapterError,
    CrewAILLMGatewayAdapter,
    CrewAIToolUseNotSupportedError,
)
from app.llm.gateway import LLMGateway


class ExampleOutput(BaseModel):
    answer: str


def make_gateway() -> Mock:
    return Mock(
        spec=LLMGateway
    )


def make_adapter(
    gateway,
    *,
    stop=None,
):
    adapter = (
        CrewAILLMGatewayAdapter(
            gateway=gateway,
            model="test-model",
        )
    )

    if stop is not None:
        adapter.stop = stop

    return adapter


def test_adapter_routes_string_to_gateway():
    gateway = make_gateway()

    gateway.generate_text.return_value = (
        "Hello from gateway"
    )

    adapter = make_adapter(
        gateway
    )

    result = adapter.call(
        "Hello CrewAI"
    )

    assert (
        result
        == "Hello from gateway"
    )

    gateway.generate_text.assert_called_once_with(
        model="test-model",
        system_prompt="",
        user_prompt="Hello CrewAI",
    )


def test_adapter_normalizes_message_history():
    gateway = make_gateway()

    gateway.generate_text.return_value = (
        "Done"
    )

    adapter = make_adapter(
        gateway
    )

    adapter.call(
        [
            {
                "role": "system",
                "content": (
                    "You are a market analyst."
                ),
            },
            {
                "role": "user",
                "content": "Research gyms.",
            },
            {
                "role": "assistant",
                "content": (
                    "I need more evidence."
                ),
            },
            {
                "role": "user",
                "content": "Continue.",
            },
        ]
    )

    gateway.generate_text.assert_called_once_with(
        model="test-model",
        system_prompt=(
            "You are a market analyst."
        ),
        user_prompt=(
            "USER:\n"
            "Research gyms.\n\n"
            "ASSISTANT:\n"
            "I need more evidence.\n\n"
            "USER:\n"
            "Continue."
        ),
    )


def test_adapter_routes_structured_output():
    gateway = make_gateway()

    gateway.generate_structured.return_value = (
        ExampleOutput(
            answer="valid"
        )
    )

    adapter = make_adapter(
        gateway
    )

    result = adapter.call(
        "Give structured output",
        response_model=ExampleOutput,
    )

    parsed = (
        ExampleOutput
        .model_validate_json(result)
    )

    assert parsed.answer == "valid"

    gateway.generate_structured.assert_called_once_with(
        model="test-model",
        system_prompt="",
        user_prompt=(
            "Give structured output"
        ),
        response_model=ExampleOutput,
    )

    gateway.generate_text.assert_not_called()


def test_adapter_rejects_tool_calling():
    gateway = make_gateway()

    adapter = make_adapter(
        gateway
    )

    with pytest.raises(
        CrewAIToolUseNotSupportedError
    ):
        adapter.call(
            "Search the web",
            tools=[
                {
                    "name": "search"
                }
            ],
        )

    gateway.generate_text.assert_not_called()


def test_adapter_applies_stop_words():
    gateway = make_gateway()

    gateway.generate_text.return_value = (
        "Action: search\n"
        "Observation: hidden"
    )

    adapter = make_adapter(
        gateway,
        stop=[
            "Observation:"
        ],
    )

    result = adapter.call(
        "Research"
    )

    assert (
        result
        == "Action: search"
    )


def test_adapter_rejects_empty_messages():
    gateway = make_gateway()

    adapter = make_adapter(
        gateway
    )

    with pytest.raises(
        CrewAILLMAdapterError
    ):
        adapter.call(
            []
        )

def test_adapter_disables_native_function_calling():
    gateway = make_gateway()

    adapter = make_adapter(
        gateway
    )

    assert (
        adapter
        .supports_function_calling()
        is False
    )