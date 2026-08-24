from uuid import uuid4

import pytest
from unittest.mock import Mock

from sqlalchemy.orm import Session
from app.chat.orchestrator import (
    MissingDatabaseSessionError,
    TurnOrchestrator,
    UnsupportedExecutionModeError,
    UnsupportedIntentError,
)
from app.chat.intake_handler import (
    IntakeHandler,
)
from app.schemas.intake import (
    ClarificationQuestion,
    IntakeHandlerResult,
    IntakeHandlerStatus,
    ProfileField,
    ProfileReadinessStatus,
)
from app.schemas.chat import (
    ChatTurnStatus,
)

from app.chat.context import WorkingContext
from app.chat.orchestrator import (
    TurnOrchestrator,
    UnsupportedExecutionModeError,
    UnsupportedIntentError,
)
from app.schemas.turn import (
    ExecutionMode,
    Intent,
    SubRequest,
    TurnUnderstanding,
)



def make_context() -> WorkingContext:
    return WorkingContext(
        idea_id=uuid4(),
        idea_title="Trainer Marketplace",
        idea_state="COLLECTING_INFORMATION",
        current_user_message="Hello",
        profile_version=1,
        profile_readiness="NOT_READY",
        profile_data={},
    )


def test_orchestrator_executes_general_chat():
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

    context = make_context()

    result = TurnOrchestrator().execute(
        turn,
        context,
    )

    assert result.response_text
    assert "Trainer Marketplace" in result.response_text


def test_orchestrator_rejects_unsupported_intent():
    turn = TurnUnderstanding(
        sub_requests=[
            SubRequest(
                id="req_1",
                intent=Intent.START_ANALYSIS,
                confidence=0.95,
            )
        ],
        execution_mode=ExecutionMode.SINGLE,
        overall_confidence=0.95,
        clarification_needed=False,
    )

    context = make_context()

    with pytest.raises(UnsupportedIntentError):
        TurnOrchestrator().execute(
            turn,
            context,
        )


def test_orchestrator_rejects_non_single_mode():
    turn = TurnUnderstanding(
        sub_requests=[
            SubRequest(
                id="req_1",
                intent=Intent.GENERAL_CHAT,
                confidence=0.95,
            ),
            SubRequest(
                id="req_2",
                intent=Intent.GENERAL_CHAT,
                confidence=0.95,
            ),
        ],
        execution_mode=ExecutionMode.PARALLEL,
        overall_confidence=0.95,
        clarification_needed=False,
    )

    context = make_context()

    with pytest.raises(
        UnsupportedExecutionModeError
    ):
        TurnOrchestrator().execute(
            turn,
            context,
        )


@pytest.mark.parametrize(
    "intent",
    [
        Intent.NEW_IDEA,
        Intent.ANSWER_CLARIFICATION,
    ],
)
def test_orchestrator_routes_intake_intents(
    intent,
):
    context = make_context()

    turn = TurnUnderstanding(
        sub_requests=[
            SubRequest(
                id="req_1",
                intent=intent,
                confidence=0.95,
            )
        ],
        execution_mode=(
            ExecutionMode.SINGLE
        ),
        overall_confidence=0.95,
        clarification_needed=False,
    )

    intake_handler = Mock(
        spec=IntakeHandler
    )

    intake_handler.handle.return_value = (
        IntakeHandlerResult(
            status=(
                IntakeHandlerStatus
                .CLARIFICATION_REQUIRED
            ),
            profile_version=2,
            readiness=(
                ProfileReadinessStatus
                .NOT_READY
            ),
            clarification=(
                ClarificationQuestion(
                    field=(
                        ProfileField
                        .TARGET_CUSTOMERS
                    ),
                    question=(
                        "Who are your first "
                        "target customers?"
                    ),
                )
            ),
        )
    )

    db = Mock(
        spec=Session
    )

    orchestrator = TurnOrchestrator(
        intake_handler=(
            intake_handler
        )
    )

    result = orchestrator.execute(
        turn,
        context,
        db,
    )

    assert (
        result.status
        == (
            ChatTurnStatus
            .CLARIFICATION_REQUIRED
        )
    )

    assert (
        result.response_text
        == (
            "Who are your first "
            "target customers?"
        )
    )

    assert (
        result.clarification
        is not None
    )

    assert (
        result.clarification.field
        == (
            ProfileField
            .TARGET_CUSTOMERS
        )
    )

    assert result.profile_version == 2

    assert (
        result.profile_readiness
        == (
            ProfileReadinessStatus
            .NOT_READY
        )
    )

    intake_handler.handle.assert_called_once_with(
        db=db,
        context=context,
    )

def test_orchestrator_rejects_intake_without_db():
    context = make_context()

    turn = TurnUnderstanding(
        sub_requests=[
            SubRequest(
                id="req_1",
                intent=(
                    Intent.NEW_IDEA
                ),
                confidence=0.95,
            )
        ],
        execution_mode=(
            ExecutionMode.SINGLE
        ),
        overall_confidence=0.95,
        clarification_needed=False,
    )

    orchestrator = TurnOrchestrator()

    with pytest.raises(
        MissingDatabaseSessionError
    ):
        orchestrator.execute(
            turn,
            context,
        )