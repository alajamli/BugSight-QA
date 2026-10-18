"""Database models for BugSight QA."""

from __future__ import annotations

from datetime import datetime, timezone

import bcrypt
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    """QA tester account."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default="tester")
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    predictions = db.relationship("Prediction", backref="user", lazy=True)

    def set_password(self, password: str) -> None:
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
            "utf-8"
        )

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Prediction(db.Model):
    """A saved bug-detection prediction."""

    __tablename__ = "predictions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    filename = db.Column(db.String(255), nullable=False)
    has_bug = db.Column(db.Boolean, default=False)
    num_detections = db.Column(db.Integer, default=0)
    detections_json = db.Column(db.Text)
    image_width = db.Column(db.Integer)
    image_height = db.Column(db.Integer)
    # "image" (default, existing rows) or "video" — lets the history table
    # tell the two kinds of analysis apart and render them differently.
    media_type = db.Column(db.String(10), default="image", nullable=False)
    # Aggregate video-only stats (frames analyzed, duration, fps, class
    # distribution). Null for image predictions.
    video_summary_json = db.Column(db.Text, nullable=True)
    # Per-frame results of a video analysis. Kept out of to_dict() (it can be
    # large) and only read by the PDF report, so each user gets their own
    # latest video instead of a process-wide shared one.
    video_frames_json = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self) -> dict:
        import json

        return {
            "id": f"pred_{self.id:06d}",
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "filename": self.filename,
            "has_bug": self.has_bug,
            "num_detections": self.num_detections,
            "detections": json.loads(self.detections_json) if self.detections_json else [],
            "image_width": self.image_width,
            "image_height": self.image_height,
            "media_type": self.media_type or "image",
            "video_summary": json.loads(self.video_summary_json)
            if self.video_summary_json
            else None,
        }


def _add_missing_columns() -> None:
    """Tiny forward-only migration: create_all() never alters existing tables."""
    inspector = db.inspect(db.engine)
    existing = {c["name"] for c in inspector.get_columns("predictions")}
    if "video_frames_json" not in existing:
        db.session.execute(db.text("ALTER TABLE predictions ADD COLUMN video_frames_json TEXT"))
        db.session.commit()
    indexes = {i["name"] for i in inspector.get_indexes("predictions")}
    if "ix_predictions_timestamp" not in indexes:
        db.session.execute(
            db.text(
                "CREATE INDEX IF NOT EXISTS ix_predictions_timestamp ON predictions (timestamp)"
            )
        )
        db.session.commit()


def init_db(app) -> None:
    """Create tables and, on a fresh database, a first admin user.

    The admin password comes from BUGSIGHT_ADMIN_PASSWORD. If it is not set a
    random one is generated and logged once, instead of shipping a well-known
    default credential.
    """
    import logging
    import os
    import secrets

    log = logging.getLogger("bugsight.db")
    db.init_app(app)
    with app.app_context():
        db.create_all()
        _add_missing_columns()
        if User.query.count() == 0:
            email = os.environ.get("BUGSIGHT_ADMIN_EMAIL", "admin@bugsight.io")
            password = os.environ.get("BUGSIGHT_ADMIN_PASSWORD")
            generated = not password
            if generated:
                password = secrets.token_urlsafe(12)
            admin = User(email=email, name="Admin", role="admin")
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
            if generated:
                log.warning(
                    "Created initial admin %s with generated password: %s "
                    "(set BUGSIGHT_ADMIN_PASSWORD to choose your own)",
                    email,
                    password,
                )
        else:
            legacy = User.query.filter_by(email="admin@bugsight.io").first()
            if legacy and legacy.role == "admin" and legacy.check_password("admin123"):
                log.warning(
                    "SECURITY: admin@bugsight.io still uses the default password "
                    "'admin123' — change it."
                )
