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


def test_profile_versioning_and_metadata(client):
    idea_id = create_test_idea(client)

    initial = client.get(
        f"/api/v1/ideas/{idea_id}/profile"
    )
    assert initial.status_code == 200
    assert initial.json()["version"] == 1
    assert initial.json()["profile_data"] == {}
    assert initial.json()["profile_metadata"] == {}
    assert initial.json()["unknown_fields"] == []

    country = client.patch(
        f"/api/v1/ideas/{idea_id}/profile",
        json={"profile_data": {"target_country": "Egypt"}},
    )
    assert country.status_code == 200
    assert country.json()["version"] == 2
    assert country.json()["profile_data"] == {
        "target_country": "Egypt"
    }
    metadata = country.json()["profile_metadata"][
        "target_country"
    ]
    assert metadata["provenance"] == "USER"
    assert metadata["value_kind"] == "FACT"
    assert metadata["confidence"] == 1.0
    assert metadata["source_message_id"] is None

    budget = client.patch(
        f"/api/v1/ideas/{idea_id}/profile",
        json={
            "profile_data": {
                "budget": 300000,
                "currency": "EGP",
            }
        },
    )
    assert budget.status_code == 200
    assert budget.json()["version"] == 3
    assert budget.json()["profile_data"] == {
        "target_country": "Egypt",
        "budget": 300000,
        "currency": "EGP",
    }
    assert set(budget.json()["profile_metadata"]) == {
        "target_country",
        "budget",
        "currency",
    }


def test_profile_conflict_does_not_overwrite(client):
    idea_id = create_test_idea(client)

    first = client.patch(
        f"/api/v1/ideas/{idea_id}/profile",
        json={"profile_data": {"target_city": "Cairo"}},
    )
    assert first.status_code == 200
    assert first.json()["version"] == 2

    conflict = client.patch(
        f"/api/v1/ideas/{idea_id}/profile",
        json={"profile_data": {"target_city": "Alexandria"}},
    )
    assert conflict.status_code == 409

    current = client.get(
        f"/api/v1/ideas/{idea_id}/profile"
    ).json()
    assert current["version"] == 2
    assert current["profile_data"] == {"target_city": "Cairo"}


def test_equivalent_value_does_not_create_version(client):
    idea_id = create_test_idea(client)

    first = client.patch(
        f"/api/v1/ideas/{idea_id}/profile",
        json={"profile_data": {"target_city": "Cairo"}},
    )
    assert first.status_code == 200
    assert first.json()["version"] == 2

    repeated = client.patch(
        f"/api/v1/ideas/{idea_id}/profile",
        json={"profile_data": {"target_city": " cairo "}},
    )
    assert repeated.status_code == 200
    assert repeated.json()["version"] == 2
    assert repeated.json()["profile_data"]["target_city"] == "Cairo"


def test_profile_rejects_unsupported_field(client):
    idea_id = create_test_idea(client)

    response = client.patch(
        f"/api/v1/ideas/{idea_id}/profile",
        json={"profile_data": {"favorite_color": "Blue"}},
    )
    assert response.status_code == 422

    current = client.get(
        f"/api/v1/ideas/{idea_id}/profile"
    ).json()
    assert current["version"] == 1
    assert current["profile_data"] == {}


def test_profile_rejects_invalid_budget(client):
    idea_id = create_test_idea(client)

    response = client.patch(
        f"/api/v1/ideas/{idea_id}/profile",
        json={"profile_data": {"budget": "a lot"}},
    )
    assert response.status_code == 422

    current = client.get(
        f"/api/v1/ideas/{idea_id}/profile"
    ).json()
    assert current["version"] == 1
    assert current["profile_data"] == {}


def test_conflicting_patch_is_atomic(client):
    idea_id = create_test_idea(client)

    first = client.patch(
        f"/api/v1/ideas/{idea_id}/profile",
        json={"profile_data": {"target_city": "Cairo"}},
    )
    assert first.status_code == 200

    conflict = client.patch(
        f"/api/v1/ideas/{idea_id}/profile",
        json={
            "profile_data": {
                "target_city": "Alexandria",
                "budget": 300000,
            }
        },
    )
    assert conflict.status_code == 409

    current = client.get(
        f"/api/v1/ideas/{idea_id}/profile"
    ).json()
    assert current["version"] == 2
    assert current["profile_data"] == {"target_city": "Cairo"}
