def create_test_idea(client) -> str:
    response = client.post(
        "/api/v1/ideas",
        json={
            "title": "Chat Test Idea",
            "description": "An idea created for testing persistent chat messages.",
        },
    )

    assert response.status_code == 201

    return response.json()["id"]


def test_create_and_read_messages(client):
    idea_id = create_test_idea(client)

    first_response = client.post(
        f"/api/v1/ideas/{idea_id}/messages",
        json={
            "content": "The target market is Egypt."
        },
    )

    print(first_response.status_code)
    print(first_response.json())

    assert first_response.status_code == 201
    assert first_response.json()["role"] == "user"
    assert (
        first_response.json()["content"]
        == "The target market is Egypt."
    )

    second_response = client.post(
        f"/api/v1/ideas/{idea_id}/messages",
        json={
            "content": "The customers are small restaurants."
        },
    )

    assert second_response.status_code == 201

    history_response = client.get(
        f"/api/v1/ideas/{idea_id}/messages"
    )

    assert history_response.status_code == 200

    messages = history_response.json()

    assert len(messages) == 2

    assert messages[0]["content"] == "The target market is Egypt."
    assert (
        messages[1]["content"]
        == "The customers are small restaurants."
    )


    def test_create_message_for_missing_idea_returns_404(client):
        response = client.post(
            "/api/v1/ideas/11111111-1111-1111-1111-111111111111/messages",
            json={
                "content": "This should not be saved."
            },
        )

        assert response.status_code == 404
        assert response.json() == {
            "detail": "Idea not found"
        }