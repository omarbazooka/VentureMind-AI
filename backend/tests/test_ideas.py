from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_idea_returns_created_idea():
    payload = {
        "title": "Food Waste AI",
        "description": "An AI platform that helps restaurants reduce food waste.",
    }
    response = client.post("/api/v1/ideas", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["description"] == payload["description"]
    assert "id" in data


#Failure Test
def test_create_idea_rejects_invalid_payload():
    payload = {
        "title": "AI",
        "description": "short",
    }

    response = client.post("/api/v1/ideas", json=payload)

    assert response.status_code == 422


# Missing Field Test
def test_create_idea_rejects_missing_description():
    payload = {
        "title": "Food Waste AI",
    }

    response = client.post("/api/v1/ideas", json=payload)

    assert response.status_code == 422


def test_create_and_get_idea(client):
    create_response = client.post(
        "/api/v1/ideas",
        json={
            "title": "Restaurant AI",
            "description": "AI platform for helping restaurants improve operations.",
        },
    )

    assert create_response.status_code == 201

    created_idea = create_response.json()

    assert created_idea["title"] == "Restaurant AI"
    assert (
        created_idea["description"]
        == "AI platform for helping restaurants improve operations."
    )
    assert "id" in created_idea

    idea_id = created_idea["id"]

    get_response = client.get(
        f"/api/v1/ideas/{idea_id}"
    )

    assert get_response.status_code == 200

    fetched_idea = get_response.json()

    assert fetched_idea["id"] == idea_id
    assert fetched_idea["title"] == "Restaurant AI"
    assert (
        fetched_idea["description"]
        == "AI platform for helping restaurants improve operations."
    )