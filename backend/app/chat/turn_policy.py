from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.turn import TurnUnderstanding


DEFAULT_MIN_CONFIDENCE = 0.70


class TurnPolicyAction(StrEnum):
    ACCEPT = "ACCEPT"
    CLARIFY = "CLARIFY"


class TurnPolicyDecision(BaseModel):
    action: TurnPolicyAction

    reasons: list[str] = Field(
        default_factory=list,
    )


def evaluate_turn(
    turn: TurnUnderstanding,
    *,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> TurnPolicyDecision:
    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError(
            "min_confidence must be between 0 and 1"
        )

    reasons: list[str] = []

    if turn.clarification_needed:
        reasons.append(
            "model_requested_clarification"
        )

    if turn.overall_confidence < min_confidence:
        reasons.append(
            "low_overall_confidence"
        )

    low_confidence_requests = [
        request.id
        for request in turn.sub_requests
        if request.confidence < min_confidence
    ]

    if low_confidence_requests:
        reasons.append(
            "low_subrequest_confidence:"
            + ",".join(low_confidence_requests)
        )

    if reasons:
        return TurnPolicyDecision(
            action=TurnPolicyAction.CLARIFY,
            reasons=reasons,
        )

    return TurnPolicyDecision(
        action=TurnPolicyAction.ACCEPT,
    )