from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import _verify_token, get_current_user
from app.core.config import settings
from app.core.database import engine
from app.main import app
from app.models.idea import Idea
from app.models.idea_profile import IdeaProfile

client = TestClient(app)


def test_auth_bypass_disabled_by_default():
    """Verify that by default, X-Dev-User-Id header is not honored as an auth bypass."""
    dev_id = str(uuid4())
    assert settings.enable_dev_auth_bypass is False

    with pytest.raises(Exception) as exc_info:
        get_current_user(authorization=None, x_dev_user_id=dev_id)
    assert "Missing Authorization header" in str(exc_info.value.detail)


def test_idea_creation_with_and_without_owner():
    """Unauthenticated idea creation leaves owner_user_id None for legacy/demo compatibility."""
    resp1 = client.post(
        "/api/v1/ideas",
        json={"title": "Public Idea", "description": "Accessible to demo viewers"},
    )
    assert resp1.status_code == 201
    d1 = resp1.json()
    assert d1["owner_user_id"] is None

    user_id = str(uuid4())
    old_bypass = settings.enable_dev_auth_bypass
    try:
        settings.enable_dev_auth_bypass = True
        resp2 = client.post(
            "/api/v1/ideas",
            headers={"X-Dev-User-Id": user_id},
            json={"title": "Private Idea", "description": "Owned by authenticated user"},
        )
        assert resp2.status_code == 201
        d2 = resp2.json()
        assert d2["owner_user_id"] == user_id
    finally:
        settings.enable_dev_auth_bypass = old_bypass


def test_idea_ownership_access_control():
    """User B cannot access private idea owned by User A."""
    user_a = uuid4()
    user_b = uuid4()

    with Session(engine) as db:
        idea_a = Idea(
            title="User A Secret Project",
            raw_initial_idea="Proprietary tech for logistics",
            owner_user_id=user_a,
        )
        db.add(idea_a)
        db.commit()
        db.refresh(idea_a)
        idea_a_id = idea_a.id

    old_bypass = settings.enable_dev_auth_bypass
    try:
        settings.enable_dev_auth_bypass = True

        resp_b = client.get(
            f"/api/v1/ideas/{idea_a_id}",
            headers={"X-Dev-User-Id": str(user_b)},
        )
        assert resp_b.status_code == 403
        assert "permission" in resp_b.json()["detail"].lower()

        resp_anon = client.get(f"/api/v1/ideas/{idea_a_id}")
        assert resp_anon.status_code == 403

        resp_a = client.get(
            f"/api/v1/ideas/{idea_a_id}",
            headers={"X-Dev-User-Id": str(user_a)},
        )
        assert resp_a.status_code == 200
        assert resp_a.json()["id"] == str(idea_a_id)

    finally:
        settings.enable_dev_auth_bypass = old_bypass


def test_list_ideas_scoped_to_owner():
    """Idea listing returns only the user's ideas plus unowned demo ideas."""
    user_1 = uuid4()
    user_2 = uuid4()

    with Session(engine) as db:
        i1 = Idea(
            title="User 1 Idea",
            raw_initial_idea="SaaS idea for user 1",
            owner_user_id=user_1,
        )
        i2 = Idea(
            title="User 2 Idea",
            raw_initial_idea="SaaS idea for user 2",
            owner_user_id=user_2,
        )
        i_public = Idea(
            title="Demo Idea",
            raw_initial_idea="Public demo idea",
            owner_user_id=None,
        )
        db.add_all([i1, i2, i_public])
        db.commit()

    old_bypass = settings.enable_dev_auth_bypass
    try:
        settings.enable_dev_auth_bypass = True

        resp1 = client.get(
            "/api/v1/ideas",
            headers={"X-Dev-User-Id": str(user_1)},
        )
        assert resp1.status_code == 200
        titles_1 = {i["title"] for i in resp1.json()}
        assert "User 1 Idea" in titles_1
        assert "Demo Idea" in titles_1
        assert "User 2 Idea" not in titles_1

        resp2 = client.get(
            "/api/v1/ideas",
            headers={"X-Dev-User-Id": str(user_2)},
        )
        assert resp2.status_code == 200
        titles_2 = {i["title"] for i in resp2.json()}
        assert "User 2 Idea" in titles_2
        assert "Demo Idea" in titles_2
        assert "User 1 Idea" not in titles_2

    finally:
        settings.enable_dev_auth_bypass = old_bypass


def test_owned_idea_workspace_endpoints_reject_other_users():
    """Ownership must protect chat, profile, analysis, report, and reanalysis surfaces."""
    owner_id = uuid4()
    other_user_id = uuid4()

    with Session(engine) as db:
        idea = Idea(
            title="Private Workspace",
            raw_initial_idea="Owner-only venture data",
            owner_user_id=owner_id,
        )
        db.add(idea)
        db.flush()
        db.add(
            IdeaProfile(
                idea_id=idea.id,
                version=1,
                readiness="NOT_READY",
                profile_data={},
                profile_metadata={},
                unknown_fields=[],
            )
        )
        db.commit()
        idea_id = idea.id

    old_bypass = settings.enable_dev_auth_bypass
    try:
        settings.enable_dev_auth_bypass = True
        other_headers = {"X-Dev-User-Id": str(other_user_id)}
        owner_headers = {"X-Dev-User-Id": str(owner_id)}

        protected_requests = (
            ("get", f"/api/v1/ideas/{idea_id}/messages", None),
            ("get", f"/api/v1/ideas/{idea_id}/profile", None),
            ("get", f"/api/v1/ideas/{idea_id}/analysis/progress", None),
            ("get", f"/api/v1/ideas/{idea_id}/report/latest", None),
            (
                "post",
                f"/api/v1/ideas/{idea_id}/reanalyze",
                {"reason": "Unauthorized attempt"},
            ),
            (
                "get",
                f"/api/v1/ideas/{idea_id}/report/compare?v1=1&v2=2",
                None,
            ),
        )

        for method, url, payload in protected_requests:
            response = client.request(
                method,
                url,
                headers=other_headers,
                json=payload,
            )
            assert response.status_code == 403, (method, url, response.text)

        owner_progress = client.get(
            f"/api/v1/ideas/{idea_id}/analysis/progress",
            headers=owner_headers,
        )
        assert owner_progress.status_code == 200
        assert owner_progress.json()["run_status"] == "NOT_STARTED"

    finally:
        settings.enable_dev_auth_bypass = old_bypass


def test_hs256_token_verification(monkeypatch):
    """Test symmetric HS256 JWT decoding when configured."""
    from pydantic import SecretStr

    secret_key = "test-secret-key-32-bytes-long!!!!"
    user_id = str(uuid4())
    token = jwt.encode(
        {"sub": user_id, "email": "test@venturemind.ai", "aud": "authenticated"},
        secret_key,
        algorithm="HS256",
    )

    monkeypatch.setattr(settings, "supabase_jwt_secret", SecretStr(secret_key))
    payload = _verify_token(token)
    assert payload["sub"] == user_id
    assert payload["email"] == "test@venturemind.ai"
