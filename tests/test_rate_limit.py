"""Rate-limiting tests, isolated from test_api.py.

These need TESTING=False (the opposite of the rest of the suite) so the
Flask-Limiter exempt_when() short-circuit does NOT kick in and the real
5-per-minute login limit is actually exercised.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.api.app import AppState, create_app  # noqa: E402


@pytest.fixture
def client():
    app = create_app(
        AppState(weights_path="does-not-exist.pt"),
        config_overrides={
            # Deliberately NOT TESTING=True: that flag exempts requests from
            # rate limiting everywhere else in the suite, which is exactly
            # what we don't want here.
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "JWT_SECRET_KEY": "test-secret-key-not-for-production",
        },
    )
    return app.test_client()


def test_login_is_rate_limited_after_five_attempts_per_minute(client) -> None:
    for _ in range(5):
        r = client.post(
            "/api/auth/login",
            json={"email": "nobody@bugsight.io", "password": "wrong"},
        )
        # Wrong credentials against a non-existent user -> still a normal 401,
        # not yet rate limited.
        assert r.status_code == 401

    # The 6th attempt within the same minute must be blocked.
    r = client.post(
        "/api/auth/login",
        json={"email": "nobody@bugsight.io", "password": "wrong"},
    )
    assert r.status_code == 429
