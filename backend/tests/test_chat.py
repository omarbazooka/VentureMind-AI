from app.api.v1.chat import get_chat_controller
from app.chat.controller import ChatTurnResult
from app.llm.gateway import LLMGatewayError
from app.main import app
from app.schemas.chat import ChatTurnStatus
from app.schemas.turn import (
    ExecutionMode,
    Intent,
    SubRequest,
    TurnUnderstanding,
)


def create_test_idea(client) -> str:
    response = client.post(
        "/api/v1/ideas",
        json={
            "title": "Chat Test Idea",
            "description": (
                "An idea created for testing "
                "persistent chat messages."
            ),
        },
    )

    assert response.status_code == 201

    return response.json()["id"]


def build_general_chat_turn() -> TurnUnderstanding:
    return TurnUnderstanding(
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


class FakeChatController:
    def handle_message(
        self,
        user_message,
        context,
    ):
        return ChatTurnResult(
            status=ChatTurnStatus.COMPLETED,
            response_text="Hi from VentureMind.",
            turn_understanding=build_general_chat_turn(),
        )


class FailingChatController:
    def handle_message(
        self,
        user_message,
        context,
    ):
        raise LLMGatewayError(
            "provider failed"
        )


def test_create_message_persists_user_and_assistant(
    client,
):
    idea_id = create_test_idea(
        client
    )

    app.dependency_overrides[
        get_chat_controller
    ] = lambda: FakeChatController()

    try:
        response = client.post(
            f"/api/v1/ideas/{idea_id}/messages",
            json={
                "content": "Hello"
            },
        )

        assert response.status_code == 201

        data = response.json()

        assert data["status"] == "COMPLETED"

        assert (
            data["user_message"]["role"]
            == "user"
        )

        assert (
            data["user_message"]["content"]
            == "Hello"
        )

        assert (
            data["assistant_message"]["role"]
            == "assistant"
        )

        assert (
            data["assistant_message"]["content"]
            == "Hi from VentureMind."
        )

        history_response = client.get(
            f"/api/v1/ideas/{idea_id}/messages"
        )

        assert history_response.status_code == 200

        messages = history_response.json()

        assert len(messages) == 2

        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"

        assert messages[1]["role"] == "assistant"
        assert (
            messages[1]["content"]
            == "Hi from VentureMind."
        )

    finally:
        app.dependency_overrides.pop(
            get_chat_controller,
            None,
        )


def test_create_message_for_missing_idea_returns_404(
    client,
):
    response = client.post(
        "/api/v1/ideas/"
        "11111111-1111-1111-1111-111111111111"
        "/messages",
        json={
            "content": "This should not be saved."
        },
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "Idea not found"
    }


def test_ai_failure_preserves_user_message(
    client,
):
    idea_id = create_test_idea(
        client
    )

    app.dependency_overrides[
        get_chat_controller
    ] = lambda: FailingChatController()

    try:
        response = client.post(
            f"/api/v1/ideas/{idea_id}/messages",
            json={
                "content": "Hello"
            },
        )

        assert response.status_code == 502

        assert response.json() == {
            "detail": (
                "AI service failed to process "
                "the message"
            )
        }

        history_response = client.get(
            f"/api/v1/ideas/{idea_id}/messages"
        )

        assert history_response.status_code == 200

        messages = history_response.json()

        assert len(messages) == 1

        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"

    finally:
        app.dependency_overrides.pop(
            get_chat_controller,
            None,
        )