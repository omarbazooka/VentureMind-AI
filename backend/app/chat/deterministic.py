from enum import StrEnum

from app.schemas.turn import (
    ExecutionMode,
    Intent,
    SubRequest,
    TurnUnderstanding,
)


class ExplicitAction(StrEnum):
    START_ANALYSIS = "START_ANALYSIS"

def build_turn_from_explicit_action(
    action: ExplicitAction
) -> TurnUnderstanding:

    if action == ExplicitAction.START_ANALYSIS:
        return TurnUnderstanding(
            sub_requests = [
                SubRequest(
                    id="req_1",
                    intent = Intent.START_ANALYSIS,
                    confidence=1.0,
                )
            ],
            execution_mode = ExecutionMode.SINGLE,
            overall_confidence = 1.0,
            clarification_needed = False,
        )
    raise ValueError(
        f"Unsupported explicit action: {action}"
    )
