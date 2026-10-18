"""Startup security checks, DB migration, metrics caching and stats aggregation."""

from __future__ import annotations

import json
import os
import sqlite3

import pytest

from src.api.app import AppState, create_app
from src.api.models import Prediction, User, db

MEMORY_DB = {"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"}


def _app(tmp_path=None, weights="missing.pt", **overrides):
    config = {"TESTING": True, "JWT_SECRET_KEY": "x" * 40, **MEMORY_DB, **overrides}
    return create_app(AppState(weights_path=str(weights)), config)


# ── Startup security ───────────────────────────────────────────


def test_production_refuses_placeholder_jwt_secret(monkeypatch) -> None:
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("BUGSIGHT_WARMUP", "0")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        create_app(AppState(weights_path="missing.pt"), MEMORY_DB)


def test_production_accepts_real_jwt_secret(monkeypatch) -> None:
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("JWT_SECRET", "a-real-secret-" + "x" * 32)
    monkeypatch.setenv("BUGSIGHT_WARMUP", "0")
    app = create_app(AppState(weights_path="missing.pt"), MEMORY_DB)
    assert app is not None


def test_development_only_warns_on_placeholder_secret(monkeypatch) -> None:
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("BUGSIGHT_WARMUP", "0")
    assert create_app(AppState(weights_path="missing.pt"), MEMORY_DB) is not None


# ── Initial admin account ──────────────────────────────────────


def test_initial_admin_uses_configured_password(monkeypatch) -> None:
    monkeypatch.setenv("BUGSIGHT_ADMIN_EMAIL", "boss@test.local")
    monkeypatch.setenv("BUGSIGHT_ADMIN_PASSWORD", "chosen-password-1")
    app = _app()
    client = app.test_client()
    ok = client.post(
        "/api/auth/login", json={"email": "boss@test.local", "password": "chosen-password-1"}
    )
    assert ok.status_code == 200
    assert ok.get_json()["user"]["role"] == "admin"
    legacy = client.post(
        "/api/auth/login", json={"email": "boss@test.local", "password": "admin123"}
    )
    assert legacy.status_code == 401


def test_initial_admin_gets_random_password_when_unset(monkeypatch, caplog) -> None:
    monkeypatch.delenv("BUGSIGHT_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("BUGSIGHT_ADMIN_EMAIL", raising=False)
    with caplog.at_level("WARNING", logger="bugsight.db"):
        app = _app()
    assert "generated password" in caplog.text
    client = app.test_client()
    r = client.post("/api/auth/login", json={"email": "admin@bugsight.io", "password": "admin123"})
    assert r.status_code == 401


# ── Migration of an existing database ──────────────────────────


def test_existing_database_gets_new_column(tmp_path) -> None:
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE predictions (id INTEGER PRIMARY KEY, user_id INTEGER, "
        "filename VARCHAR(255) NOT NULL, has_bug BOOLEAN, num_detections INTEGER, "
        "detections_json TEXT, image_width INTEGER, image_height INTEGER, "
        "media_type VARCHAR(10) NOT NULL DEFAULT 'image', video_summary_json TEXT, "
        "timestamp DATETIME)"
    )
    conn.execute("INSERT INTO predictions (filename, has_bug) VALUES ('legacy.png', 1)")
    conn.commit()
    conn.close()

    app = _app(SQLALCHEMY_DATABASE_URI=f"sqlite:///{path.as_posix()}")
    with app.app_context():
        columns = {c["name"] for c in db.inspect(db.engine).get_columns("predictions")}
        assert "video_frames_json" in columns
        assert Prediction.query.count() == 1  # old rows survive the migration
    # running init again must be a no-op
    _app(SQLALCHEMY_DATABASE_URI=f"sqlite:///{path.as_posix()}")


# ── Metrics ────────────────────────────────────────────────────


def _write_results(path, precision) -> None:
    path.write_text(
        "epoch,  metrics/precision(B),  metrics/recall(B),  metrics/mAP50(B),"
        "  metrics/mAP50-95(B),  fitness\n"
        f"1, {precision}, 0.5, 0.6, 0.4, 0.45\n",
        encoding="utf-8",
    )


def test_metrics_read_results_next_to_weights_and_refresh(tmp_path) -> None:
    run = tmp_path / "run"
    (run / "weights").mkdir(parents=True)
    results = run / "results.csv"
    _write_results(results, 0.71)

    app = _app(weights=run / "weights" / "best.pt")
    client = app.test_client()
    first = client.get("/api/metrics").get_json()
    assert first["precision"] == 0.71
    assert first["recall"] == 0.5

    # unchanged file -> served from cache, same answer
    assert client.get("/api/metrics").get_json() == first

    # changed file (new mtime) -> cache invalidated
    _write_results(results, 0.93)
    stat = results.stat()
    os.utime(results, (stat.st_atime, stat.st_mtime + 5))
    assert client.get("/api/metrics").get_json()["precision"] == 0.93


def test_metrics_endpoint_always_returns_class_names(tmp_path) -> None:
    app = _app(weights=tmp_path / "nowhere" / "weights" / "best.pt")
    body = app.test_client().get("/api/metrics").get_json()
    assert set(body) >= {"precision", "recall", "mAP50", "mAP50_95", "fitness", "class_names"}


# ── Health ─────────────────────────────────────────────────────


def test_health_reports_database_state() -> None:
    app = _app()
    r = app.test_client().get("/api/health")
    assert r.status_code == 200
    body = r.get_json()
    assert body["db_connected"] is True and body["status"] == "ok"


# ── Stats aggregation in SQL ───────────────────────────────────


def test_stats_aggregate_images_and_videos_per_user() -> None:
    app = _app()
    client = app.test_client()
    tokens = {}
    for name in ("one", "two"):
        r = client.post(
            "/api/auth/register",
            json={"email": f"{name}@test.local", "name": name, "password": "secret123"},
        )
        tokens[name] = {"Authorization": f"Bearer {r.get_json()['token']}"}

    with app.app_context():
        one = User.query.filter_by(email="one@test.local").first()
        two = User.query.filter_by(email="two@test.local").first()
        detections = [{"class_name": "screen_tear"}, {"class_name": "z_fighting"}]
        db.session.add_all(
            [
                Prediction(
                    user_id=one.id,
                    filename="a.png",
                    has_bug=True,
                    detections_json=json.dumps(detections),
                ),
                Prediction(user_id=one.id, filename="b.png", has_bug=False),
                Prediction(
                    user_id=one.id,
                    filename="v.mp4",
                    has_bug=True,
                    media_type="video",
                    video_summary_json=json.dumps({"class_distribution": {"screen_tear": 4}}),
                ),
                Prediction(user_id=two.id, filename="c.png", has_bug=False),
            ]
        )
        db.session.commit()

    stats = client.get("/api/stats", headers=tokens["one"]).get_json()
    assert stats["total_analyses"] == 3
    assert stats["bug_detected"] == 2
    assert stats["clean"] == 1
    assert stats["bug_rate"] == round(2 / 3, 4)
    assert stats["class_distribution"]["screen_tear"] == 5
    assert stats["class_distribution"]["z_fighting"] == 1

    other = client.get("/api/stats", headers=tokens["two"]).get_json()
    assert other["total_analyses"] == 1 and other["bug_detected"] == 0
