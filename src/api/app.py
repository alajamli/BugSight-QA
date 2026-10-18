"""Flask REST API for BugSight QA with auth + database + PDF reports + video."""

from __future__ import annotations

import io
import json
import logging
import os
import tempfile
import threading
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy.orm import joinedload

from src.api.models import Prediction, User, db, init_db

logger = logging.getLogger("bugsight.api")

_RUNS_DIR = Path(__file__).resolve().parents[2] / "runs" / "detect" / "runs"


def _default_weights() -> str:
    """Newest trained model (v2 preferred), falling back to the v1 baseline."""
    for name in ("bugsight_yolov8n_v2", "bugsight_yolov8n"):
        candidate = _RUNS_DIR / name / "weights" / "best.pt"
        if candidate.exists():
            return str(candidate)
    return str(_RUNS_DIR / "bugsight_yolov8n" / "weights" / "best.pt")


DEFAULT_WEIGHTS = os.environ.get("BUGSIGHT_WEIGHTS") or _default_weights()
DEFAULT_DATA_YAML = os.environ.get(
    "BUGSIGHT_DATA_YAML",
    str(Path(__file__).resolve().parents[2] / "data" / "processed" / "data.yaml"),
)

BUG_CLASSES = [
    "missing_texture",
    "texture_glitch",
    "z_fighting",
    "screen_tear",
    "uv_stretch",
    "color_corruption",
]


ALLOWED_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
ALLOWED_VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
VIDEO_BATCH_SIZE = 8
MAX_FRAMES_LIMIT = 300
PLACEHOLDER_SECRETS = {
    "change-me-to-a-random-32-byte-secret",
    "bugsight-secret-key-2026-please-override-me",
}


def _extract_detections(result) -> list[dict]:
    """Convert one Ultralytics result into the API's detection dicts."""
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return []
    names = result.names
    return [
        {
            "class_id": int(cls),
            "class_name": names[int(cls)],
            "confidence": round(float(conf), 4),
            "bbox_xyxy": [round(v, 2) for v in xyxy],
        }
        for xyxy, conf, cls in zip(
            boxes.xyxy.tolist(), boxes.conf.tolist(), boxes.cls.tolist(), strict=True
        )
    ]


def _parse_float(value, default: float, lo: float, hi: float) -> float:
    """Parse a form value as a float clamped to [lo, hi]; ValueError if not a number."""
    if value is None or value == "":
        return default
    number = float(value)
    if number != number:  # NaN
        raise ValueError("not a number")
    return min(hi, max(lo, number))


def _ext_allowed(filename: str, allowed: set[str]) -> bool:
    return Path(filename).suffix.lower() in allowed


def _video_meta(path: str) -> tuple[int, float]:
    """Return (frame_count, fps); frame_count is 0 when the container does not say."""
    cap = cv2.VideoCapture(path)
    try:
        return int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), cap.get(cv2.CAP_PROP_FPS) or 30
    finally:
        cap.release()


def _iter_sampled_frames(path: str, max_frames: int, total: int):
    """Yield (frame_index, frame) for at most max_frames evenly spaced frames.

    Frames that are not sampled are only grab()-ed (demuxed, not converted to
    a BGR array), which is much cheaper than a full read() for every frame.
    It is a generator so callers can infer in small batches instead of holding
    every sampled frame in memory.
    """
    wanted = None
    if total > 0:
        count = min(max_frames, total)
        wanted = {int(i * total / count) for i in range(count)}
    cap = cv2.VideoCapture(path)
    try:
        idx = sent = 0
        while sent < max_frames and cap.grab():
            if wanted is None or idx in wanted:
                ok, frame = cap.retrieve()
                if ok:
                    sent += 1
                    yield idx, frame
            idx += 1
    finally:
        cap.release()


class AppState:
    def __init__(self, weights_path: str | None = None, data_yaml: str | None = None) -> None:
        self.weights_path = weights_path or DEFAULT_WEIGHTS
        self.data_yaml = data_yaml or DEFAULT_DATA_YAML
        self._model = None
        # Ultralytics models are not thread-safe and gunicorn runs --threads 2.
        self._lock = threading.Lock()

    def ensure_model(self):
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None or not Path(self.weights_path).exists():
                return
            from ultralytics import YOLO

            self._model = YOLO(self.weights_path)

    def predict_batch(self, images, conf=0.25):
        """Run inference on a list of images; returns one detection list per image."""
        self.ensure_model()
        if self._model is None:
            raise RuntimeError("Model not available")
        with self._lock:
            results = self._model.predict(source=images, conf=conf, verbose=False)
        return [_extract_detections(r) for r in results]

    def predict(self, image, filename, conf=0.25):
        detections = self.predict_batch([image], conf=conf)[0]
        h, w = image.shape[:2]
        return detections, w, h


def create_app(state: AppState | None = None, config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    # Tests (and anything else that wants isolation) pass config_overrides with
    # TESTING=True + an in-memory DB, so pytest never touches the real
    # bugsight.db file on disk. In Docker, DATABASE_URL points at a mounted
    # volume so analyses survive `docker compose down` / rebuilds — previously
    # this always resolved to a path inside the container's writable layer,
    # which is wiped every time the container is recreated.
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///bugsight.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JWT_SECRET_KEY"] = os.environ.get(
        "JWT_SECRET", "bugsight-secret-key-2026-please-override-me"
    )
    # Reject uploads above this size before they are buffered (default 200 MB).
    app.config["MAX_CONTENT_LENGTH"] = (
        int(os.environ.get("BUGSIGHT_MAX_UPLOAD_MB", "200")) * 1024 * 1024
    )
    # Previously undefined -> defaulted to 15 minutes, which silently broke the
    # frontend once the access token expired (no refresh flow existed).
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(
        minutes=int(os.environ.get("JWT_ACCESS_EXPIRES_MIN", "60"))
    )
    app.config["JWT_REFRESH_TOKEN_EXPIRES"] = timedelta(
        days=int(os.environ.get("JWT_REFRESH_EXPIRES_DAYS", "30"))
    )
    if config_overrides:
        app.config.update(config_overrides)

    # A known/placeholder signing secret lets anyone forge admin tokens, so
    # refuse to boot with one in production (gunicorn sets FLASK_ENV=production
    # in the Dockerfile); in development just warn.
    if app.config["JWT_SECRET_KEY"] in PLACEHOLDER_SECRETS and not app.config.get("TESTING"):
        if os.environ.get("FLASK_ENV") == "production":
            raise RuntimeError(
                "JWT_SECRET is unset or a placeholder. Set it to a random string, e.g. "
                'python -c "import secrets; print(secrets.token_hex(32))"'
            )
        logger.warning("Using a placeholder JWT secret — fine for local dev only.")

    CORS(app, origins=os.environ.get("BUGSIGHT_CORS_ORIGINS", "*").split(","))

    JWTManager(app)  # registers the extension on `app`; no direct use needed
    init_db(app)
    state = state or AppState()

    # Load the model at startup so the first user request is not the slow one.
    if not app.config.get("TESTING") and os.environ.get("BUGSIGHT_WARMUP", "1") != "0":
        try:
            state.ensure_model()
        except Exception:
            logger.exception("Model warm-up failed; it will be retried on first request")

    @app.errorhandler(413)
    def too_large(_error):
        limit_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        return jsonify({"error": f"File too large (max {limit_mb} MB)"}), 413

    # Nothing previously stopped repeated /api/auth/login attempts, so the
    # endpoint was open to unlimited password brute-forcing.
    #
    # NOTE: don't pass enabled=False for tests. Flask-Limiter's init_app()
    # returns early when disabled and never registers itself in
    # app.extensions, so the Limiter instance is only kept alive by the local
    # `limiter` variable here — once create_app() returns, it gets garbage
    # collected, and the weakref each @limiter.limit(...) decorator holds to
    # it goes stale, raising ReferenceError on every request. exempt_when
    # keeps the limiter fully initialized (and therefore alive) while simply
    # skipping the check during tests.
    limiter = Limiter(
        get_remote_address,
        app=app,
        storage_uri="memory://",
        default_limits_exempt_when=lambda: app.config.get("TESTING", False),
    )

    def admin_required(view):
        """Allow access only to an authenticated user whose role is admin."""

        @wraps(view)
        @jwt_required()
        def wrapped(*args, **kwargs):
            current_user = db.session.get(User, int(get_jwt_identity()))
            if not current_user or current_user.role != "admin":
                return jsonify({"error": "Admin access required"}), 403
            return view(*args, **kwargs)

        return wrapped

    def _stats(user_id=None):
        """Aggregate stats, optionally for one user.

        Totals are computed in SQL; only the two JSON columns are fetched (not
        whole ORM rows) to build the per-class distribution.
        """
        base = db.session.query(Prediction)
        if user_id is not None:
            base = base.filter(Prediction.user_id == user_id)
        total = base.with_entities(db.func.count(Prediction.id)).scalar() or 0
        buggy = (
            base.filter(Prediction.has_bug.is_(True))
            .with_entities(db.func.count(Prediction.id))
            .scalar()
            or 0
        )
        class_counts = dict.fromkeys(BUG_CLASSES, 0)
        rows = base.filter(Prediction.has_bug.is_(True)).with_entities(
            Prediction.detections_json, Prediction.video_summary_json
        )
        for detections_json, video_summary_json in rows:
            if detections_json:
                for detection in json.loads(detections_json):
                    name = detection.get("class_name", "")
                    if name in class_counts:
                        class_counts[name] += 1
            elif video_summary_json:
                distribution = json.loads(video_summary_json).get("class_distribution", {})
                for name, count in distribution.items():
                    if name in class_counts:
                        class_counts[name] += int(count or 0)
        return {
            "total_analyses": total,
            "bug_detected": buggy,
            "clean": total - buggy,
            "bug_rate": round(buggy / total, 4) if total else 0.0,
            "class_distribution": class_counts,
        }

    def _system_status():
        database_uri = app.config.get("SQLALCHEMY_DATABASE_URI", "")
        database_path = None
        if database_uri.startswith("sqlite:///") and ":memory:" not in database_uri:
            database_path = Path(database_uri.replace("sqlite:///", "", 1))
            if not database_path.is_absolute():
                database_path = Path(app.instance_path) / database_path
        database_size = (
            database_path.stat().st_size if database_path and database_path.exists() else 0
        )
        storage_quota = int(os.environ.get("BUGSIGHT_STORAGE_QUOTA_BYTES", str(10 * 1024**3)))
        try:
            db.session.execute(db.text("SELECT 1"))
            db_connected = True
        except Exception:
            db_connected = False
        return {
            "model_loaded": state._model is not None,
            "weights_exists": Path(state.weights_path).exists(),
            "db_connected": db_connected,
            "database_size_bytes": database_size,
            "storage_quota_bytes": storage_quota,
            "storage_used_bytes": database_size,
            "storage_usage_ratio": round(database_size / storage_quota, 4) if storage_quota else 0,
            "storage_note": "Les médias sont analysés en mémoire; seules les métadonnées sont persistées.",
        }

    # ── Auth: register ─────────────────────────────────────

    @app.post("/api/auth/register")
    @limiter.limit("10 per hour", exempt_when=lambda: app.config.get("TESTING", False))
    def register():
        data = request.get_json() or {}
        email = data.get("email", "").strip().lower()
        name = data.get("name", "").strip()
        password = data.get("password", "")
        if not email or not name or not password:
            return jsonify({"error": "Email, name and password required"}), 400
        if len(password) < 6:
            return jsonify({"error": "Password must be 6+ characters"}), 400
        if User.query.filter_by(email=email).first():
            return jsonify({"error": "Email already registered"}), 409
        user = User(email=email, name=name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        return jsonify(
            {"token": token, "refresh_token": refresh_token, "user": user.to_dict()}
        ), 201

    # ── Auth: login ────────────────────────────────────────

    @app.post("/api/auth/login")
    @limiter.limit("5 per minute", exempt_when=lambda: app.config.get("TESTING", False))
    def login():
        data = request.get_json() or {}
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            return jsonify({"error": "Invalid credentials"}), 401
        token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        return jsonify({"token": token, "refresh_token": refresh_token, "user": user.to_dict()})

    # ── Auth: refresh ──────────────────────────────────────

    @app.post("/api/auth/refresh")
    @jwt_required(refresh=True)
    def refresh():
        user_id = get_jwt_identity()
        new_token = create_access_token(identity=user_id)
        return jsonify({"token": new_token})

    # ── Auth: me ───────────────────────────────────────────

    @app.get("/api/auth/me")
    @jwt_required()
    def me():
        user_id = int(get_jwt_identity())
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404
        return jsonify(user.to_dict())

    # ── Health ─────────────────────────────────────────────

    @app.get("/api/health")
    def health():
        try:
            db.session.execute(db.text("SELECT 1"))
            db_connected = True
        except Exception:
            db_connected = False
        body = {
            "status": "ok" if db_connected else "degraded",
            "model_loaded": state._model is not None,
            "weights_exists": Path(state.weights_path).exists(),
            "db_connected": db_connected,
        }
        return jsonify(body), (200 if db_connected else 503)

    # ── Metrics ───────────────────────────────────────────

    _metrics_cache: dict = {}
    _EMPTY_METRICS = {
        "precision": 0,
        "recall": 0,
        "mAP50": 0,
        "mAP50_95": 0,
        "fitness": 0,
        "class_names": BUG_CLASSES,
    }

    def _find_results_csv():
        """results.csv of the run that produced the loaded weights, else the newest one."""
        beside_weights = Path(state.weights_path).parent.parent / "results.csv"
        if beside_weights.exists():
            return beside_weights
        candidates = list(Path("/app/models").rglob("results.csv")) + list(
            Path("runs").rglob("results.csv")
        )
        return max(candidates, key=lambda p: p.stat().st_mtime, default=None)

    @app.get("/api/metrics")
    def metrics():
        import csv

        # Re-parse only when the file changed, instead of walking the disk and
        # reading the CSV on every dashboard load.
        try:
            path = _find_results_csv()
            if path is None:
                return jsonify(_EMPTY_METRICS)
            mtime = path.stat().st_mtime
            cached = _metrics_cache.get("entry")
            if cached and cached[0] == (str(path), mtime):
                return jsonify(cached[1])
            with open(path, newline="") as f:
                rows = list(csv.DictReader(f))
            if not rows:
                return jsonify(_EMPTY_METRICS)
            last = {k.strip(): v for k, v in rows[-1].items()}

            def _f(key):
                try:
                    return round(float(last.get(key, 0)), 4)
                except (TypeError, ValueError):
                    return 0.0

            body = {
                "precision": _f("metrics/precision(B)"),
                "recall": _f("metrics/recall(B)"),
                "mAP50": _f("metrics/mAP50(B)"),
                "mAP50_95": _f("metrics/mAP50-95(B)"),
                "fitness": _f("fitness"),
                "class_names": BUG_CLASSES,
            }
            _metrics_cache["entry"] = ((str(path), mtime), body)
            return jsonify(body)
        except Exception as e:
            logger.warning(f"results.csv error: {e}")
            return jsonify(_EMPTY_METRICS)

    # ── Predict (image) ────────────────────────────────────

    @app.post("/api/predict")
    @jwt_required()
    def predict():
        if "image" not in request.files:
            return jsonify({"error": "No image provided"}), 400
        file = request.files["image"]
        if not file.filename:
            return jsonify({"error": "Empty filename"}), 400
        if not _ext_allowed(file.filename, ALLOWED_IMAGE_EXT):
            return jsonify(
                {
                    "error": f"Unsupported image type (allowed: {', '.join(sorted(ALLOWED_IMAGE_EXT))})"
                }
            ), 400
        try:
            conf = _parse_float(request.form.get("confidence"), 0.25, 0.01, 1.0)
        except ValueError:
            return jsonify({"error": "confidence must be a number"}), 400
        filebytes = np.frombuffer(file.read(), np.uint8)
        image = cv2.imdecode(filebytes, cv2.IMREAD_COLOR)
        if image is None:
            return jsonify({"error": "Could not decode image"}), 400
        try:
            detections, w, h = state.predict(image, file.filename, conf=conf)
            user_id = int(get_jwt_identity())
            record = Prediction(
                user_id=user_id,
                filename=file.filename,
                has_bug=len(detections) > 0,
                num_detections=len(detections),
                detections_json=json.dumps(detections),
                image_width=w,
                image_height=h,
            )
            db.session.add(record)
            db.session.commit()
            return jsonify(record.to_dict())
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 503
        except Exception:
            logger.exception("Prediction failed")
            return jsonify({"error": "Prediction failed"}), 500

    # ── Predict video ──────────────────────────────────────

    @app.post("/api/predict-video")
    @jwt_required()
    def predict_video():
        if "video" not in request.files:
            return jsonify({"error": "No video provided"}), 400
        file = request.files["video"]
        if not file.filename:
            return jsonify({"error": "Empty filename"}), 400
        if not _ext_allowed(file.filename, ALLOWED_VIDEO_EXT):
            return jsonify(
                {
                    "error": f"Unsupported video type (allowed: {', '.join(sorted(ALLOWED_VIDEO_EXT))})"
                }
            ), 400
        try:
            conf = _parse_float(request.form.get("confidence"), 0.25, 0.01, 1.0)
            max_frames = int(_parse_float(request.form.get("max_frames"), 60, 1, MAX_FRAMES_LIMIT))
        except ValueError:
            return jsonify({"error": "confidence and max_frames must be numbers"}), 400

        # Check the model before touching the disk.
        state.ensure_model()
        if state._model is None:
            return jsonify({"error": "Model not available"}), 503

        suffix = Path(file.filename).suffix.lower() or ".mp4"
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        try:
            file.save(tmp_path)
            total_frames, fps = _video_meta(tmp_path)

            frames_results = []

            def _flush(batch):
                if not batch:
                    return
                all_detections = state.predict_batch([f for _, f in batch], conf=conf)
                for (frame_idx, _), detections in zip(batch, all_detections, strict=True):
                    frames_results.append(
                        {
                            "frame": len(frames_results),
                            "timestamp": round(frame_idx / fps, 2),
                            "has_bug": len(detections) > 0,
                            "num_detections": len(detections),
                            "detections": detections,
                        }
                    )

            batch = []
            for item in _iter_sampled_frames(tmp_path, max_frames, total_frames):
                batch.append(item)
                if len(batch) >= VIDEO_BATCH_SIZE:
                    _flush(batch)
                    batch = []
            _flush(batch)
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 503
        except Exception:
            logger.exception("Video analysis failed")
            return jsonify({"error": "Video analysis failed"}), 500
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        if not frames_results:
            return jsonify({"error": "Could not read any frame from the video"}), 400
        if total_frames <= 0:
            total_frames = frames_results[-1]["frame"] + 1

        total_analyzed = len(frames_results)
        buggy_frames = sum(1 for f in frames_results if f["has_bug"])
        total_detections = sum(f["num_detections"] for f in frames_results)

        class_counts = dict.fromkeys(BUG_CLASSES, 0)
        for f in frames_results:
            for d in f["detections"]:
                cn = d.get("class_name", "")
                if cn in class_counts:
                    class_counts[cn] += 1

        video_summary = {
            "total_frames": total_frames,
            "analyzed_frames": total_analyzed,
            "buggy_frames": buggy_frames,
            "bug_rate": round(buggy_frames / total_analyzed, 4) if total_analyzed else 0,
            "fps": round(fps, 1),
            "duration": round(total_frames / fps, 1) if fps else 0,
            "class_distribution": class_counts,
        }

        # Frames are persisted with the analysis (per user) so the PDF report can
        # include *this user's* latest video, even across workers and restarts.
        record = Prediction(
            user_id=int(get_jwt_identity()),
            filename=file.filename,
            has_bug=buggy_frames > 0,
            num_detections=total_detections,
            media_type="video",
            video_summary_json=json.dumps(video_summary),
            video_frames_json=json.dumps(frames_results),
        )
        db.session.add(record)
        db.session.commit()

        return jsonify({**video_summary, "frames": frames_results, "id": record.to_dict()["id"]})

    # ── Admin: global dashboard ────────────────────────────

    @app.get("/api/admin/overview")
    @admin_required
    def admin_overview():
        users = User.query.order_by(User.created_at.desc()).all()
        stats_data = _stats()
        return jsonify(
            {
                "stats": stats_data,
                "users": [user.to_dict() for user in users],
                "analyses_count": stats_data["total_analyses"],
                "system": _system_status(),
            }
        )

    @app.get("/api/admin/users")
    @admin_required
    def admin_users():
        return jsonify(
            {
                "users": [
                    user.to_dict() for user in User.query.order_by(User.created_at.desc()).all()
                ]
            }
        )

    @app.patch("/api/admin/users/<int:user_id>/role")
    @admin_required
    def admin_update_role(user_id):
        target = db.session.get(User, user_id)
        if not target:
            return jsonify({"error": "User not found"}), 404
        role = (request.get_json() or {}).get("role")
        if role not in {"admin", "tester"}:
            return jsonify({"error": "Role must be admin or tester"}), 400
        current_id = int(get_jwt_identity())
        if target.id == current_id and role != "admin":
            return jsonify({"error": "You cannot remove your own admin role"}), 400
        target.role = role
        db.session.commit()
        return jsonify({"user": target.to_dict()})

    @app.delete("/api/admin/users/<int:user_id>")
    @admin_required
    def admin_delete_user(user_id):
        target = db.session.get(User, user_id)
        if not target:
            return jsonify({"error": "User not found"}), 404
        if target.id == int(get_jwt_identity()):
            return jsonify({"error": "You cannot delete your own account"}), 400
        Prediction.query.filter_by(user_id=target.id).delete(synchronize_session=False)
        db.session.delete(target)
        db.session.commit()
        return jsonify({"deleted": True, "user_id": user_id})

    @app.get("/api/admin/analyses")
    @admin_required
    def admin_analyses():
        # joinedload: one query instead of one extra query per row for .user
        predictions = (
            Prediction.query.options(joinedload(Prediction.user))
            .order_by(Prediction.timestamp.desc())
            .limit(500)
            .all()
        )
        return jsonify(
            {
                "predictions": [
                    {
                        **prediction.to_dict(),
                        "user": prediction.user.to_dict() if prediction.user else None,
                    }
                    for prediction in predictions
                ]
            }
        )

    @app.get("/api/admin/system")
    @admin_required
    def admin_system():
        return jsonify(_system_status())

    # ── History ────────────────────────────────────────────

    @app.get("/api/history")
    @jwt_required()
    def history():
        """The user's analyses, newest first.

        Query params: limit (1-500, default 100), offset, q (filename contains),
        status (bug|clean), type (image|video). `total` is the count matching
        the filters, so clients can paginate.
        """
        user_id = int(get_jwt_identity())
        try:
            limit = min(500, max(1, int(request.args.get("limit", 100))))
            offset = max(0, int(request.args.get("offset", 0)))
        except ValueError:
            return jsonify({"error": "limit and offset must be integers"}), 400

        query = Prediction.query.filter_by(user_id=user_id)
        text = request.args.get("q", "").strip()
        if text:
            escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            query = query.filter(Prediction.filename.ilike(f"%{escaped}%", escape="\\"))
        status = request.args.get("status")
        if status in {"bug", "clean"}:
            query = query.filter(Prediction.has_bug.is_(status == "bug"))
        media = request.args.get("type")
        if media in {"image", "video"}:
            query = query.filter(Prediction.media_type == media)

        total = query.count()
        preds = (
            query.order_by(Prediction.timestamp.desc(), Prediction.id.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )
        return jsonify({"predictions": [p.to_dict() for p in preds], "total": total})

    @app.delete("/api/history/<pred_id>")
    @jwt_required()
    def delete_history_item(pred_id):
        """Delete one of the caller's own analyses (accepts `pred_000012` or `12`)."""
        raw = pred_id[5:] if pred_id.startswith("pred_") else pred_id
        if not raw.isdigit():
            return jsonify({"error": "Analysis not found"}), 404
        record = Prediction.query.filter_by(id=int(raw), user_id=int(get_jwt_identity())).first()
        if not record:
            return jsonify({"error": "Analysis not found"}), 404
        db.session.delete(record)
        db.session.commit()
        return jsonify({"deleted": True, "id": pred_id})

    # ── Stats ──────────────────────────────────────────────

    @app.get("/api/stats")
    @jwt_required()
    def stats():
        user_id = int(get_jwt_identity())
        return jsonify(_stats(user_id))

    # ── Export PDF report (with optional video) ──────────

    @app.get("/api/report")
    @jwt_required()
    def download_report():
        from src.api.report_generator import generate_report

        user_id = int(get_jwt_identity())
        user = db.session.get(User, user_id)
        preds = (
            Prediction.query.filter_by(user_id=user_id)
            .order_by(Prediction.timestamp.desc())
            .limit(100)
            .all()
        )

        stats_data = {
            "total_analyses": len(preds),
            "bug_detected": sum(1 for p in preds if p.has_bug),
            "clean": sum(1 for p in preds if not p.has_bug),
        }

        # Check if video result should be included
        video_result = None
        include_video = request.args.get("include_video", "false").lower() == "true"
        if include_video:
            # This user's own most recent video analysis (never another user's).
            latest_video = (
                Prediction.query.filter_by(user_id=user_id, media_type="video")
                .filter(Prediction.video_frames_json.isnot(None))
                .order_by(Prediction.timestamp.desc())
                .first()
            )
            if latest_video:
                video_result = {
                    **json.loads(latest_video.video_summary_json),
                    "frames": json.loads(latest_video.video_frames_json),
                }

        pdf_bytes = generate_report(
            predictions=[p.to_dict() for p in preds],
            user_name=user.name if user else "QA Tester",
            stats=stats_data,
            video_result=video_result,
            lang=request.args.get("lang", "fr"),
        )

        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=f"bugsight_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        )

    app.config["state"] = state
    return app


app = create_app()
