from unittest.mock import Mock
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.idea import Idea
from app.models.idea_profile import IdeaProfile
from app.schemas.analysis import AnalysisRunStatus
from app.services.analysis_run import start_analysis_run


def create_test_idea(client) -> str:
    response = client.post(
        "/api/v1/ideas",
        json={
            "title": "Analysis Test Idea",
            "description": (
                "A test idea for analysis runs."
            ),
        },
    )

    assert response.status_code == 201
    return response.json()["id"]


def make_profile_ready(
    client,
    idea_id: str,
) -> dict:
    response = client.patch(
        f"/api/v1/ideas/{idea_id}/profile",
        json={
            "profile_data": {
                "idea_description": (
                    "A SaaS platform for independent gyms."
                ),
                "target_customers": [
                    "Independent gym owners"
                ],
                "target_country": "Egypt",
            }
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["readiness"] == "READY_FOR_ANALYSIS"
    return data


def test_start_analysis_creates_queued_run(
    client,
):
    idea_id = create_test_idea(client)
    profile = make_profile_ready(
        client,
        idea_id,
    )

    response = client.post(
        f"/api/v1/ideas/{idea_id}/analysis"
    )

    assert response.status_code == 202

    data = response.json()
    assert data["idea_id"] == idea_id
    assert data["status"] == "QUEUED"
    assert (
        data["profile_version"]
        == profile["version"]
    )
    assert data["run_id"]
    assert data["profile_id"]
    assert data["created_at"]


def test_start_analysis_rejects_not_ready_profile(
    client,
):
    idea_id = create_test_idea(client)

    response = client.post(
        f"/api/v1/ideas/{idea_id}/analysis"
    )

    assert response.status_code == 409

    detail = response.json()["detail"]
    assert detail["readiness"] == "NOT_READY"
    assert detail["missing_critical_fields"]


def test_start_analysis_rejects_duplicate_active_run(
    client,
):
    idea_id = create_test_idea(client)
    make_profile_ready(
        client,
        idea_id,
    )

    first_response = client.post(
        f"/api/v1/ideas/{idea_id}/analysis"
    )
    assert first_response.status_code == 202

    second_response = client.post(
        f"/api/v1/ideas/{idea_id}/analysis"
    )

    assert second_response.status_code == 409

    detail = second_response.json()["detail"]
    assert (
        detail["run_id"]
        == first_response.json()["run_id"]
    )
    assert detail["status"] == "QUEUED"


def test_start_analysis_for_missing_idea_returns_404(
    client,
):
    response = client.post(
        "/api/v1/ideas/"
        "11111111-1111-1111-1111-111111111111"
        "/analysis"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Idea not found"
    }


def test_start_analysis_freezes_exact_profile_snapshot():
    idea_id = uuid4()
    profile_id = uuid4()

    idea = Idea(
        id=idea_id,
        title="Gym SaaS",
        raw_initial_idea="Gym management SaaS",
    )

    profile_metadata = {
        "idea_description": {
            "provenance": "USER"
        },
        "target_customers": {
            "provenance": "USER"
        },
        "target_country": {
            "provenance": "USER"
        },
    }

    profile = IdeaProfile(
        id=profile_id,
        idea_id=idea_id,
        version=4,
        readiness="READY_FOR_ANALYSIS",
        profile_data={
            "idea_description": "Gym SaaS",
            "target_customers": [
                "Independent gym owners"
            ],
            "target_country": "Egypt",
        },
        profile_metadata=profile_metadata,
        unknown_fields=["budget"],
    )

    db = Mock(spec=Session)
    db.get.return_value = idea
    db.scalar.side_effect = [
        None,
        profile,
    ]

    analysis_run = start_analysis_run(
        db=db,
        idea_id=idea_id,
    )

    assert analysis_run.idea_id == idea_id
    assert analysis_run.profile_id == profile_id
    assert analysis_run.profile_version == 4
    assert (
        analysis_run.status
        == AnalysisRunStatus.QUEUED.value
    )
    assert analysis_run.profile_snapshot == {
        "readiness": "READY_FOR_ANALYSIS",
        "profile_data": profile.profile_data,
        "profile_metadata": profile_metadata,
        "unknown_fields": ["budget"],
    }

    db.add.assert_called_once_with(
        analysis_run
    )
    db.flush.assert_called_once_with()
