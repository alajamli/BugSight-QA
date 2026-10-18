"""Tests for video sampling, upload validation and per-user video reports."""

from __future__ import annotations

import io
from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from src.api.app import AppState, _extract_detections, create_app
from src.api.models import db


class StubModel:
    """Flags every frame as buggy; records how many frames it was given."""

    def __init__(self) -> None:
        self.frames_seen = 0

    def predict(self, source, conf, verbose):
        images = source if isinstance(source, list) else [source]
        self.frames_seen += len(images)
        box = SimpleNamespace(
            xyxy=SimpleNamespace(tolist=lambda: [[1.0, 2.0, 30.0, 40.0]]),
            conf=SimpleNamespace(tolist=lambda: [0.9]),
            cls=SimpleNamespace(tolist=lambda: [3.0]),
        )
        result = SimpleNamespace(boxes=_Boxes(box), names={3: "screen_tear"})
        return [result for _ in images]


class _Boxes:
    def __init__(self, box) -> None:
        self.xyxy = box.xyxy
        self.conf = box.conf
        self.cls = box.cls

    def __len__(self) -> int:
        return 1


@pytest.fixture
def stub_app(tmp_path):
    state = AppState(weights_path=str(tmp_path / "w.pt"))
    state._model = StubModel()
    app = create_app(
        state,
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "JWT_SECRET_KEY": "test-secret-key-0123456789abcdef-long",
            "MAX_CONTENT_LENGTH": 2 * 1024 * 1024,
        },
    )
    with app.app_context():
        db.drop_all()
        db.create_all()
    app.stub_model = state._model
    return app


def _register(client, email):
    r = client.post(
        "/api/auth/register", json={"email": email, "name": email, "password": "secret123"}
    )
    return {"Authorization": f"Bearer {r.get_json()['token']}"}


def _make_video(path, n_frames=40) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    for i in range(n_frames):
        writer.write(np.full((48, 64, 3), i * 5 % 255, np.uint8))
    writer.release()


def test_extract_detections_shape() -> None:
    result = StubModel().predict([np.zeros((4, 4, 3))], 0.25, False)[0]
    dets = _extract_detections(result)
    assert dets == [
        {
            "class_id": 3,
            "class_name": "screen_tear",
            "confidence": 0.9,
            "bbox_xyxy": [1.0, 2.0, 30.0, 40.0],
        }
    ]


def test_video_samples_only_requested_frames(stub_app, tmp_path) -> None:
    video = tmp_path / "clip.avi"
    _make_video(video, n_frames=40)
    client = stub_app.test_client()
    headers = _register(client, "a@test.local")
    r = client.post(
        "/api/predict-video",
        data={"video": (io.BytesIO(video.read_bytes()), "clip.avi"), "max_frames": "10"},
        content_type="multipart/form-data",
        headers=headers,
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["analyzed_frames"] == 10
    assert body["buggy_frames"] == 10
    assert stub_app.stub_model.frames_seen == 10
    assert body["class_distribution"]["screen_tear"] == 10


def test_report_only_uses_own_video(stub_app, tmp_path) -> None:
    video = tmp_path / "clip.avi"
    _make_video(video)
    client = stub_app.test_client()
    alice = _register(client, "alice@test.local")
    bob = _register(client, "bob@test.local")
    client.post(
        "/api/predict-video",
        data={"video": (io.BytesIO(video.read_bytes()), "clip.avi")},
        content_type="multipart/form-data",
        headers=alice,
    )
    with_video = client.get("/api/report?include_video=true", headers=alice)
    without_video = client.get("/api/report?include_video=true", headers=bob)
    assert with_video.status_code == without_video.status_code == 200
    # Bob never analysed a video, so his PDF must not contain Alice's section.
    assert len(with_video.data) > len(without_video.data)


@pytest.mark.parametrize(
    "form,expected",
    [({"confidence": "abc"}, 400), ({"confidence": "nan"}, 400)],
)
def test_predict_rejects_bad_confidence(stub_app, form, expected) -> None:
    client = stub_app.test_client()
    headers = _register(client, "c@test.local")
    r = client.post(
        "/api/predict",
        data={"image": (io.BytesIO(b"x"), "a.png"), **form},
        content_type="multipart/form-data",
        headers=headers,
    )
    assert r.status_code == expected


def test_predict_rejects_unsupported_extension(stub_app) -> None:
    client = stub_app.test_client()
    headers = _register(client, "d@test.local")
    r = client.post(
        "/api/predict",
        data={"image": (io.BytesIO(b"x"), "payload.exe")},
        content_type="multipart/form-data",
        headers=headers,
    )
    assert r.status_code == 400


def test_oversized_upload_returns_413(stub_app) -> None:
    client = stub_app.test_client()
    headers = _register(client, "e@test.local")
    r = client.post(
        "/api/predict",
        data={"image": (io.BytesIO(b"0" * (3 * 1024 * 1024)), "big.png")},
        content_type="multipart/form-data",
        headers=headers,
    )
    assert r.status_code == 413
    assert "error" in r.get_json()


def test_history_pagination_params(stub_app) -> None:
    client = stub_app.test_client()
    headers = _register(client, "f@test.local")
    assert client.get("/api/history?limit=5&offset=0", headers=headers).status_code == 200
    assert client.get("/api/history?limit=abc", headers=headers).status_code == 400


@pytest.mark.parametrize("lang", ["en", "fr", "xx"])
def test_report_supports_both_languages(stub_app, lang) -> None:
    client = stub_app.test_client()
    headers = _register(client, f"r-{lang}@test.local")
    r = client.get(f"/api/report?lang={lang}", headers=headers)
    assert r.status_code == 200
    assert r.data.startswith(b"%PDF")


def test_report_texts_cover_same_keys() -> None:
    from src.api.report_generator import BUG_CLASSES, GUIDES, TEXTS

    assert set(TEXTS["fr"]) == set(TEXTS["en"])
    for lang in ("fr", "en"):
        assert set(GUIDES[lang]) == set(BUG_CLASSES)
        for guide in GUIDES[lang].values():
            assert set(guide) == {"title", "description", "impact", "checks", "fix", "priority"}


def _add_predictions(app, email, rows):
    from src.api.models import Prediction, User

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        for name, has_bug, media in rows:
            db.session.add(
                Prediction(user_id=user.id, filename=name, has_bug=has_bug, media_type=media)
            )
        db.session.commit()


def test_history_filters_and_total(stub_app) -> None:
    client = stub_app.test_client()
    headers = _register(client, "h@test.local")
    _add_predictions(
        stub_app,
        "h@test.local",
        [
            ("menu_01.png", True, "image"),
            ("menu_02.png", False, "image"),
            ("100%_run.mp4", True, "video"),
            ("level.mp4", False, "video"),
        ],
    )

    def get(qs):
        return client.get(f"/api/history?{qs}", headers=headers).get_json()

    assert get("")["total"] == 4
    assert get("status=bug")["total"] == 2
    assert get("type=video")["total"] == 2
    assert get("q=MENU")["total"] == 2
    assert get("q=menu&status=clean")["total"] == 1
    # LIKE wildcards in the search text are matched literally
    assert get("q=%25")["total"] == 1
    assert get("q=_")["total"] == 3  # the three names with a literal underscore, not "any char"
    page = get("limit=1&offset=1")
    assert page["total"] == 4 and len(page["predictions"]) == 1


def test_delete_history_item_only_own(stub_app) -> None:
    client = stub_app.test_client()
    alice = _register(client, "al@test.local")
    bob = _register(client, "bo@test.local")
    _add_predictions(stub_app, "al@test.local", [("a.png", True, "image")])
    item = client.get("/api/history", headers=alice).get_json()["predictions"][0]

    assert client.delete(f"/api/history/{item['id']}", headers=bob).status_code == 404
    assert client.delete(f"/api/history/{item['id']}", headers=alice).status_code == 200
    assert client.get("/api/history", headers=alice).get_json()["total"] == 0
    assert client.delete("/api/history/abc", headers=alice).status_code == 404
