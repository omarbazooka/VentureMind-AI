import pytest
from pydantic import ValidationError

from app.schemas.turn import Intent, SubRequest
from app.schemas.turn import (
    ExecutionMode,
    Intent,
    SubRequest,
    TurnUnderstanding,
)

def test_sub_request_accepts_valid_data():
    sub_request = SubRequest(
        id="req_1",
        intent=Intent.CHANGE_ASSUMPTION,
        payload={
            "field": "budget",
            "value": 500000,
        },
        confidence=0.95,
    )

    assert sub_request.id == "req_1"
    assert sub_request.intent == Intent.CHANGE_ASSUMPTION
    assert sub_request.payload["value"] == 500000
    assert sub_request.confidence == 0.95
    assert sub_request.depends_on == []


def test_sub_request_rejects_invalid_confidence():
    with pytest.raises(ValidationError):
        SubRequest(
            id="req_1",
            intent=Intent.GENERAL_CHAT,
            confidence=1.5,
        )


def test_sub_request_rejects_unknown_intent():
    with pytest.raises(ValidationError):
        SubRequest(
            id="req_1",
            intent="DELETE_DATABASE",
            confidence=0.9,
        )


def test_turn_understanding_accepts_single_request():
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

    assert turn.execution_mode == ExecutionMode.SINGLE
    assert len(turn.sub_requests) == 1


def test_turn_understanding_accepts_dependency():
    turn = TurnUnderstanding(
        sub_requests=[
            SubRequest(
                id="req_1",
                intent=Intent.CHANGE_ASSUMPTION,
                payload={
                    "field": "budget",
                    "value": 500000,
                },
                confidence=0.96,
            ),
            SubRequest(
                id="req_2",
                intent=Intent.RUN_SCENARIO,
                confidence=0.91,
                depends_on=["req_1"],
            ),
        ],
        execution_mode=ExecutionMode.SEQUENTIAL,
        overall_confidence=0.93,
        clarification_needed=False,
    )

    assert len(turn.sub_requests) == 2
    assert turn.sub_requests[1].depends_on == ["req_1"]


def test_turn_understanding_rejects_unknown_dependency():
    with pytest.raises(ValidationError):
        TurnUnderstanding(
            sub_requests=[
                SubRequest(
                    id="req_1",
                    intent=Intent.RUN_SCENARIO,
                    confidence=0.9,
                    depends_on=["req_999"],
                )
            ],
            execution_mode=ExecutionMode.SINGLE,
            overall_confidence=0.9,
            clarification_needed=False,
        )


def test_turn_understanding_rejects_duplicate_ids():
    with pytest.raises(ValidationError):
        TurnUnderstanding(
            sub_requests=[
                SubRequest(
                    id="req_1",
                    intent=Intent.GENERAL_CHAT,
                    confidence=0.9,
                ),
                SubRequest(
                    id="req_1",
                    intent=Intent.GENERAL_CHAT,
                    confidence=0.9,
                ),
            ],
            execution_mode=ExecutionMode.SEQUENTIAL,
            overall_confidence=0.9,
            clarification_needed=False,
        )


def test_single_execution_rejects_multiple_requests():
    with pytest.raises(ValidationError):
        TurnUnderstanding(
            sub_requests=[
                SubRequest(
                    id="req_1",
                    intent=Intent.GENERAL_CHAT,
                    confidence=0.9,
                ),
                SubRequest(
                    id="req_2",
                    intent=Intent.GENERAL_CHAT,
                    confidence=0.9,
                ),
            ],
            execution_mode=ExecutionMode.SINGLE,
            overall_confidence=0.9,
            clarification_needed=False,
        )