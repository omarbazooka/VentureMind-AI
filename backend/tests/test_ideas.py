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
