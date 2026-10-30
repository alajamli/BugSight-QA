"""Tests for the PDF report: severity, video incidents, image/video separation, thumbnails."""

from __future__ import annotations

import io
import os

import cv2
import numpy as np
import pytest

from src.api import report_generator
from src.api.app import AppState, create_app
from src.api.models import Prediction, db
from src.api.report_generator import _incidents, generate_report, severity
from tests.test_video_and_limits import StubModel, _make_video, _register


@pytest.fixture
def app(tmp_path):
    state = AppState(weights_path=str(tmp_path / "w.pt"))
    state._model = StubModel()
    flask_app = create_app(
        state,
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "JWT_SECRET_KEY": "test-secret-key-0123456789abcdef-long",
            "MEDIA_DIR": str(tmp_path / "media"),
        },
    )
    with flask_app.app_context():
        db.drop_all()
        db.create_all()
    return flask_app


def _png(width=64, height=48) -> bytes:
    ok, buf = cv2.imencode(".png", np.full((height, width, 3), 120, np.uint8))
    assert ok
    return buf.tobytes()


@pytest.mark.parametrize(
    "name,conf,area,expected",
    [
        ("missing_texture", 0.9, 15.0, "critical"),  # 3 + 1 + 1
        ("missing_texture", 0.9, 2.0, "high"),  # 3 + 1
        ("screen_tear", 0.5, 2.0, "low"),  # 2
        ("screen_tear", 0.9, 2.0, "medium"),  # 2 + 1
        ("z_fighting", 0.3, None, "low"),  # 3 - 1
    ],
)
def test_severity_rule(name, conf, area, expected) -> None:
    assert severity(name, conf, area) == expected


def test_incidents_group_consecutive_buggy_frames() -> None:
    def frame(i, bug, conf=0.8):
        dets = [{"class_name": "screen_tear", "confidence": conf}] if bug else []
        return {"frame": i, "timestamp": i * 0.5, "has_bug": bug, "detections": dets}

    frames = [frame(0, True, 0.6), frame(1, True, 0.9), frame(2, False), frame(3, True)]
    incidents = _incidents(frames)
    assert len(incidents) == 2
    assert (incidents[0]["start"], incidents[0]["end"], incidents[0]["frames"]) == (0.0, 0.5, 2)
    assert incidents[0]["classes"] == {"screen_tear": 0.9}


def test_image_part_ignores_video_analyses(monkeypatch) -> None:
    seen = {}
    real = report_generator._image_elements

    def spy(predictions, *args):
        seen["names"] = [p["filename"] for p in predictions]
        return real(predictions, *args)

    monkeypatch.setattr(report_generator, "_image_elements", spy)
    generate_report(
        [
            {"filename": "shot.png", "media_type": "image", "has_bug": False, "detections": []},
            {"filename": "clip.mp4", "media_type": "video", "has_bug": True, "detections": []},
        ],
        report_type="image",
    )
    assert seen["names"] == ["shot.png"]


def test_report_with_unicode_name_and_thumbnail(tmp_path) -> None:
    thumb = tmp_path / "t.jpg"
    cv2.imwrite(str(thumb), np.full((48, 64, 3), 200, np.uint8))
    prediction = {
        "id": "pred_000001",
        "filename": "الشبكة_capture.png",
        "media_type": "image",
        "has_bug": True,
        "image_width": 64,
        "image_height": 48,
        "confidence_threshold": 0.5,
        "timestamp": "2026-10-30T10:00:00",
        "thumbnail_path": str(thumb),
        "detections": [
            {"class_name": "texture_glitch", "confidence": 0.84, "bbox_xyxy": [1, 2, 30, 40]}
        ],
    }
    for lang in ("fr", "en"):
        pdf = generate_report([prediction], lang=lang, report_type="image")
        assert pdf.startswith(b"%PDF")
        assert b"/Subtype /Image" in pdf  # the annotated capture is embedded


def test_predict_stores_threshold_and_thumbnail(app) -> None:
    client = app.test_client()
    headers = _register(client, "thumb@test.local")
    r = client.post(
        "/api/predict",
        data={"image": (io.BytesIO(_png()), "frame.png"), "confidence": "0.4"},
        content_type="multipart/form-data",
        headers=headers,
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["confidence_threshold"] == pytest.approx(0.4)
    record_id = int(body["id"].removeprefix("pred_"))
    thumb = os.path.join(app.config["MEDIA_DIR"], f"{record_id}.jpg")
    assert os.path.exists(thumb)

    assert client.delete(f"/api/history/{body['id']}", headers=headers).status_code == 200
    assert not os.path.exists(thumb)


@pytest.mark.parametrize("report_type", ["all", "image", "video"])
def test_report_types(app, report_type) -> None:
    client = app.test_client()
    headers = _register(client, f"type-{report_type}@test.local")
    client.post(
        "/api/predict",
        data={"image": (io.BytesIO(_png()), "frame.png")},
        content_type="multipart/form-data",
        headers=headers,
    )
    r = client.get(f"/api/report?type={report_type}&lang=fr", headers=headers)
    assert r.status_code == 200
    assert r.data.startswith(b"%PDF")
    image_embedded = b"/Subtype /Image" in r.data
    assert image_embedded == (report_type in {"all", "image"})


def test_report_rejects_unknown_type(app) -> None:
    client = app.test_client()
    headers = _register(client, "bad-type@test.local")
    assert client.get("/api/report?type=pdf", headers=headers).status_code == 400


def test_report_counts_only_images(app, monkeypatch) -> None:
    client = app.test_client()
    headers = _register(client, "mixed@test.local")
    with app.app_context():
        from src.api.models import User

        user = User.query.filter_by(email="mixed@test.local").first()
        db.session.add(Prediction(user_id=user.id, filename="a.png", media_type="image"))
        db.session.add(
            Prediction(user_id=user.id, filename="b.mp4", media_type="video", has_bug=True)
        )
        db.session.commit()
    captured = {}
    real = report_generator.generate_report

    def spy(predictions, **kwargs):
        captured["media"] = [p["media_type"] for p in predictions]
        return real(predictions, **kwargs)

    monkeypatch.setattr(report_generator, "generate_report", spy)
    assert client.get("/api/report", headers=headers).status_code == 200
    assert captured["media"] == ["image"]


def test_incident_severity_uses_frame_size() -> None:
    detection = {"class_name": "missing_texture", "confidence": 0.9, "bbox_xyxy": [0, 0, 50, 50]}
    frames = [{"frame": 0, "timestamp": 0.0, "has_bug": True, "detections": [detection]}]
    assert _incidents(frames)[0]["level"] == "high"  # area unknown: 3 + 1
    assert _incidents(frames, (100, 100))[0]["level"] == "critical"  # 25 % of the frame


def _upload_video(client, headers, tmp_path, name="clip.avi"):
    video = tmp_path / name
    _make_video(video)
    r = client.post(
        "/api/predict-video",
        data={"video": (io.BytesIO(video.read_bytes()), name), "max_frames": "10"},
        content_type="multipart/form-data",
        headers=headers,
    )
    assert r.status_code == 200, r.get_json()
    return r.get_json()


def test_video_keyframes_saved_reported_and_deleted(app, tmp_path) -> None:
    client = app.test_client()
    headers = _register(client, "video@test.local")
    body = _upload_video(client, headers, tmp_path)
    # The stub flags every frame, so the whole clip is one incident.
    assert len(body["keyframes"]) == 1
    assert (body["width"], body["height"]) == (64, 48)
    record_id = int(body["id"].removeprefix("pred_"))
    keyframe = os.path.join(app.config["MEDIA_DIR"], f"{record_id}_k1.jpg")
    assert os.path.exists(keyframe)

    r = client.get(f"/api/report?type=video&video_id={body['id']}", headers=headers)
    assert r.status_code == 200
    assert b"/Subtype /Image" in r.data  # key frame embedded

    assert client.delete(f"/api/history/{body['id']}", headers=headers).status_code == 200
    assert not os.path.exists(keyframe)


def test_video_report_only_for_own_video(app, tmp_path) -> None:
    client = app.test_client()
    alice = _register(client, "alice-v@test.local")
    bob = _register(client, "bob-v@test.local")
    body = _upload_video(client, alice, tmp_path)
    assert client.get(f"/api/report?video_id={body['id']}", headers=bob).status_code == 404
    assert client.get("/api/report?type=video&video_id=abc", headers=alice).status_code == 404
    assert client.get(f"/api/report?video_id={body['id']}", headers=alice).status_code == 200


def test_video_report_without_video_still_renders(app) -> None:
    client = app.test_client()
    headers = _register(client, "novideo@test.local")
    r = client.get("/api/report?type=video&lang=en", headers=headers)
    assert r.status_code == 200 and r.data.startswith(b"%PDF")
