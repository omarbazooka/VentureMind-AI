def create_test_idea(client) -> str:
    response = client.post(
        "/api/v1/ideas",
        json={
            "title": "Profile Test Idea",
            "description": "An idea used to test structured profile persistence.",
        },
    )

    assert response.status_code == 201

    return response.json()["id"]


def test_profile_versioning(client):
    idea_id = create_test_idea(client)

    initial_response = client.get(
        f"/api/v1/ideas/{idea_id}/profile"
    )

    assert initial_response.status_code == 200

    initial_profile = initial_response.json()

    assert initial_profile["version"] == 1
    assert initial_profile["readiness"] == "NOT_READY"
    assert initial_profile["profile_data"] == {}

    country_response = client.patch(
        f"/api/v1/ideas/{idea_id}/profile",
        json={
            "profile_data": {
                "target_country": "Egypt"
            }
        },
    )

    assert country_response.status_code == 200

    country_profile = country_response.json()

    assert country_profile["version"] == 2
    assert country_profile["profile_data"] == {
        "target_country": "Egypt"
    }

    budget_response = client.patch(
        f"/api/v1/ideas/{idea_id}/profile",
        json={
            "profile_data": {
                "budget": 300000,
                "currency": "EGP",
            }
        },
    )

    assert budget_response.status_code == 200

    updated_profile = budget_response.json()

    assert updated_profile["version"] == 3

    assert updated_profile["profile_data"] == {
        "target_country": "Egypt",
        "budget": 300000,
        "currency": "EGP",
    }

    current_response = client.get(
        f"/api/v1/ideas/{idea_id}/profile"
    )

    assert current_response.status_code == 200
    assert current_response.json()["version"] == 3