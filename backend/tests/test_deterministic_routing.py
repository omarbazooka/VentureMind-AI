from app.chat.deterministic import (
    ExplicitAction,
    build_turn_from_explicit_action,
)
from app.schemas.turn import ExecutionMode, Intent


def test_start_analysis_action_bypasses_turn_understanding():
    turn = build_turn_from_explicit_action(
        ExplicitAction.START_ANALYSIS
    )

    assert turn.execution_mode == ExecutionMode.SINGLE
    assert turn.overall_confidence == 1.0
    assert turn.clarification_needed is False

    assert len(turn.sub_requests) == 1

    request = turn.sub_requests[0]

    assert request.intent == Intent.START_ANALYSIS
    assert request.confidence == 1.0
    assert request.depends_on == []