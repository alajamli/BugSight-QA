from __future__ import annotations

import pytest

from src.api.app import AppState, create_app
from src.api.models import User, db


@pytest.fixture
def admin_app():
    app = create_app(
        AppState(weights_path="/tmp/missing-model.pt"),
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "JWT_SECRET_KEY": "test-admin-secret-key-32-bytes-long",
        },
    )
    with app.app_context():
        db.drop_all()
        db.create_all()
    return app


def token(client, email, password="secret123"):
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    return response.get_json()["token"]


def test_admin_dashboard_is_forbidden_for_tester(admin_app):
    client = admin_app.test_client()
    client.post(
        "/api/auth/register",
        json={"email": "tester@test.local", "name": "Tester", "password": "secret123"},
    )
    response = client.get(
        "/api/admin/overview",
        headers={"Authorization": f"Bearer {token(client, 'tester@test.local')}"},
    )
    assert response.status_code == 403


def test_admin_can_list_users_and_update_role(admin_app):
    client = admin_app.test_client()
    client.post(
        "/api/auth/register",
        json={"email": "admin@test.local", "name": "Admin", "password": "secret123"},
    )
    client.post(
        "/api/auth/register",
        json={"email": "tester@test.local", "name": "Tester", "password": "secret123"},
    )
    with admin_app.app_context():
        User.query.filter_by(email="admin@test.local").first().role = "admin"
        db.session.commit()
    headers = {"Authorization": f"Bearer {token(client, 'admin@test.local')}"}
    overview = client.get("/api/admin/overview", headers=headers)
    assert overview.status_code == 200
    assert len(overview.get_json()["users"]) == 2
    tester = next(
        user for user in overview.get_json()["users"] if user["email"] == "tester@test.local"
    )
    changed = client.patch(
        f"/api/admin/users/{tester['id']}/role", json={"role": "admin"}, headers=headers
    )
    assert changed.status_code == 200
    assert changed.get_json()["user"]["role"] == "admin"


def test_admin_cannot_delete_self(admin_app):
    client = admin_app.test_client()
    client.post(
        "/api/auth/register",
        json={"email": "admin@test.local", "name": "Admin", "password": "secret123"},
    )
    with admin_app.app_context():
        User.query.filter_by(email="admin@test.local").first().role = "admin"
        db.session.commit()
    headers = {"Authorization": f"Bearer {token(client, 'admin@test.local')}"}
    user_id = client.get("/api/auth/me", headers=headers).get_json()["id"]
    assert client.delete(f"/api/admin/users/{user_id}", headers=headers).status_code == 400
