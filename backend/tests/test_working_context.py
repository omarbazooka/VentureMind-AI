from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.chat.context import (
    WorkingContextError,
    build_working_context,
)


def test_build_working_context():
    idea_id = uuid4()
    session_id = uuid4()
    current_message_id = uuid4()

    idea = SimpleNamespace(
        id=idea_id,
        title="Restaurant AI",
        state="NEW",
    )

    profile = SimpleNamespace(
        version=3,
        readiness="NOT_READY",
        profile_data={
            "target_country": "Egypt",
        },
    )

    chat_session = SimpleNamespace(
        id=session_id,
    )

    messages = [
        SimpleNamespace(
            role="assistant",
            content="Who are your customers?",
        ),
        SimpleNamespace(
            role="user",
            content="Restaurants.",
        ),
    ]

    db = Mock(
        spec=Session
    )

    db.get.return_value = idea

    db.scalar.side_effect = [
        profile,
        chat_session,
    ]

    db.scalars.return_value.all.return_value = (
        messages
    )

    context = build_working_context(
        db=db,
        idea_id=idea_id,
        current_user_message="Tell me more.",
        current_message_id=current_message_id,
    )

    assert context.idea_id == idea_id
    assert context.profile_version == 3

    assert (
        context.current_user_message
        == "Tell me more."
    )

    assert len(
        context.recent_messages
    ) == 2


def test_build_working_context_rejects_missing_idea():
    db = Mock(
        spec=Session
    )

    db.get.return_value = None

    with pytest.raises(
        WorkingContextError,
        match="Idea not found",
    ):
        build_working_context(
            db=db,
            idea_id=uuid4(),
            current_user_message="Hello",
        )


def test_build_working_context_rejects_blank_message():
    db = Mock(
        spec=Session
    )

    with pytest.raises(
        ValueError,
        match="current_user_message cannot be empty",
    ):
        build_working_context(
            db=db,
            idea_id=uuid4(),
            current_user_message="   ",
        )