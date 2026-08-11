import pytest

from app.chat.turn_policy import (
    TurnPolicyAction,
    evaluate_turn,
)
from app.schemas.turn import (
    ExecutionMode,
    Intent,
    SubRequest,
    TurnUnderstanding,
)


def make_turn(
    *,
    confidence: float = 0.95,
    clarification_needed: bool = False,
) -> TurnUnderstanding:
    return TurnUnderstanding(
        sub_requests=[
            SubRequest(
                id="req_1",
                intent=Intent.GENERAL_CHAT,
                confidence=confidence,
            )
        ],
        execution_mode=ExecutionMode.SINGLE,
        overall_confidence=confidence,
        clarification_needed=clarification_needed,
    )


def test_policy_accepts_clear_turn():
    decision = evaluate_turn(
        make_turn(confidence=0.95)
    )

    assert decision.action == TurnPolicyAction.ACCEPT
    assert decision.reasons == []


def test_policy_clarifies_when_model_requests_it():
    decision = evaluate_turn(
        make_turn(
            confidence=0.95,
            clarification_needed=True,
        )
    )

    assert decision.action == TurnPolicyAction.CLARIFY
    assert "model_requested_clarification" in decision.reasons


def test_policy_clarifies_low_confidence():
    decision = evaluate_turn(
        make_turn(confidence=0.50)
    )

    assert decision.action == TurnPolicyAction.CLARIFY


def test_policy_rejects_invalid_threshold():
    with pytest.raises(ValueError):
        evaluate_turn(
            make_turn(),
            min_confidence=1.5,
        )