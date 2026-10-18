"""Unit tests for the Flask API."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.app import AppState, create_app  # noqa: E402
from src.api.models import db  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = REPO_ROOT / "runs" / "detect" / "runs" / "bugsight_yolov8n" / "weights" / "best.pt"
has_model = WEIGHTS.exists()

TEST_USER = {"email": "tester@bugsight.io", "name": "Test User", "password": "testpass123"}


@pytest.fixture(scope="module")
def app():
    # Built once per test module (not per test): Flask-Limiter tracks its
    # decorated view functions by qualified name, and recreating the Flask
    # app (and therefore the view closures) for every single test made old
    # entries go stale mid-suite, raising "weakly-referenced object no longer
    # exists". Isolation between tests is handled by _reset_db below instead.
    flask_app = create_app(
        AppState(weights_path=str(WEIGHTS)),
        config_overrides={
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "JWT_SECRET_KEY": "test-secret-key-not-for-production",
        },
    )
    return flask_app


@pytest.fixture(autouse=True)
def _reset_db(app):
    """Wipe and recreate all tables before every test for full isolation."""
    with app.app_context():
        db.drop_all()
        db.create_all()
    yield


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """A test client that already registered a user and sends a valid access token."""
    resp = client.post("/api/auth/register", json=TEST_USER)
    assert resp.status_code == 201, resp.get_json()
    token = resp.get_json()["token"]
    client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return client


# ── Health / public endpoints ───────────────────────────────


def test_health_endpoint(client) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.get_json()
    assert data["status"] == "ok"


def test_metrics_endpoint_is_public(client) -> None:
    r = client.get("/api/metrics")
    assert r.status_code == 200
    assert "class_names" in r.get_json()


# ── Auth ─────────────────────────────────────────────────────


def test_register_creates_user_and_returns_tokens(client) -> None:
    r = client.post("/api/auth/register", json=TEST_USER)
    assert r.status_code == 201
    data = r.get_json()
    assert data["user"]["email"] == TEST_USER["email"]
    assert "token" in data
    assert "refresh_token" in data


def test_register_rejects_duplicate_email(client) -> None:
    client.post("/api/auth/register", json=TEST_USER)
    r = client.post("/api/auth/register", json=TEST_USER)
    assert r.status_code == 409


def test_register_rejects_short_password(client) -> None:
    r = client.post(
        "/api/auth/register",
        json={"email": "short@bugsight.io", "name": "Short", "password": "123"},
    )
    assert r.status_code == 400


def test_login_with_correct_credentials(client) -> None:
    client.post("/api/auth/register", json=TEST_USER)
    r = client.post(
        "/api/auth/login",
        json={"email": TEST_USER["email"], "password": TEST_USER["password"]},
    )
    assert r.status_code == 200
    assert "token" in r.get_json()


def test_login_with_wrong_password_is_rejected(client) -> None:
    client.post("/api/auth/register", json=TEST_USER)
    r = client.post(
        "/api/auth/login",
        json={"email": TEST_USER["email"], "password": "wrong-password"},
    )
    assert r.status_code == 401


def test_refresh_returns_new_access_token(client) -> None:
    reg = client.post("/api/auth/register", json=TEST_USER).get_json()
    r = client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {reg['refresh_token']}"},
    )
    assert r.status_code == 200
    assert "token" in r.get_json()


def test_refresh_rejects_an_access_token(client) -> None:
    # An access token is not a refresh token; the endpoint must reject it.
    reg = client.post("/api/auth/register", json=TEST_USER).get_json()
    r = client.post(
        "/api/auth/refresh",
        headers={"Authorization": f"Bearer {reg['token']}"},
    )
    assert r.status_code == 422 or r.status_code == 401


# ── Protected endpoints require a token ─────────────────────


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/stats"),
        ("get", "/api/history"),
        ("post", "/api/predict"),
        ("get", "/api/report"),
    ],
)
def test_protected_endpoints_reject_missing_token(client, method, path) -> None:
    r = getattr(client, method)(path)
    assert r.status_code == 401


def test_stats_empty_initially(auth_client) -> None:
    r = auth_client.get("/api/stats")
    assert r.status_code == 200
    data = r.get_json()
    assert data["total_analyses"] == 0
    assert data["bug_rate"] == 0.0


def test_history_empty_initially(auth_client) -> None:
    r = auth_client.get("/api/history")
    assert r.status_code == 200
    assert r.get_json()["predictions"] == []


def test_predict_no_file(auth_client) -> None:
    r = auth_client.post("/api/predict", data={}, content_type="multipart/form-data")
    assert r.status_code == 400
    assert "error" in r.get_json()


def test_predict_invalid_image(auth_client) -> None:
    r = auth_client.post(
        "/api/predict",
        data={"image": (io.BytesIO(b"not an image"), "fake.png")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 400


@pytest.mark.skipif(not has_model, reason="Trained model not available")
def test_predict_with_real_model(auth_client) -> None:
    import cv2

    from src.data_generation.scene_generator import SceneConfig, SceneGenerator

    gen = SceneGenerator(SceneConfig(seed=5, bug_probability=1.0))
    sample = gen.generate()
    ok, buf = cv2.imencode(".png", sample.image)
    assert ok

    r = auth_client.post(
        "/api/predict",
        data={"image": (io.BytesIO(buf.tobytes()), "test.png")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 200
    data = r.get_json()
    assert data["has_bug"] is True

    r2 = auth_client.get("/api/history")
    assert len(r2.get_json()["predictions"]) == 1

    r3 = auth_client.get("/api/stats")
    assert r3.get_json()["bug_detected"] == 1
