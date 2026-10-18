# BugSight QA - Automatic Visual Bug Detection for Games

BugSight QA is an AI-assisted QA tool that detects visual rendering bugs in game
screenshots and gameplay videos with a YOLOv8 object detection model. It exposes
a REST API and a bilingual (English / French) React dashboard where QA teams
upload captures, inspect detections, keep a searchable history and export PDF
reports.

**Detected bug classes:** missing texture, texture glitch, z-fighting, screen tear,
UV stretch, color corruption.

## Features

- **Image and video analysis** with an adjustable confidence threshold. Videos are
  sampled evenly (30-300 frames), with upload progress and a cancel button.
- **History** per user: search by file name, filter by result and type, paginate,
  delete.
- **Statistics and model quality** (precision, recall, mAP) charts.
- **PDF report** with diagnosis and fix guidance for each bug class, in the
  language chosen in the UI.
- **English / French UI**, switchable at any time (saved in the browser).
- **Accounts and roles** (tester / admin), JWT access + refresh tokens, login
  rate limiting, admin dashboard (users, all analyses, system status).

## Quick start

Requirements: Python 3.10+ and Node 22+.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then edit it (see Configuration)

# Dataset + model (skip if you already have weights)
python scripts/generate_dataset.py          # -> data/processed_v2 (1500 images)
python scripts/train.py --config configs/train.yaml

# API on http://localhost:5000
python scripts/serve.py

# Dashboard on http://localhost:5173 (second terminal)
cd frontend && npm ci && npm run dev
```

`make help` lists the shortcuts (`make serve`, `make test`, `make ci`, ...). On
Windows `make` needs a tool such as Git Bash or `choco install make`.

### First login

On a brand-new database an admin account is created automatically. Set
`BUGSIGHT_ADMIN_EMAIL` / `BUGSIGHT_ADMIN_PASSWORD` to choose it; if the password is
empty a random one is generated and **printed once in the API log**. There is no
default password. Other users can register from the login page.

## Training and evaluating the model

```bash
python scripts/generate_dataset.py                  # six classes, ~250 boxes each, in data/processed_v2
python scripts/train.py --config configs/train.yaml      # CPU (estimated 2-3 h)
python scripts/train.py --config configs/train_gpu.yaml  # CUDA GPU / Colab T4 (estimated 10-20 min)
python scripts/evaluate.py                          # per-class report for the newest weights
```

- **Why a new dataset generator:** every defect is drawn visibly inside its box and
  checked against the clean scene. The previous data labelled `screen_tear` and
  `uv_stretch` over regions that looked identical to the background, which capped
  their recall at 10-25%.
- **Per-class report:** `scripts/evaluate.py` (also run at the end of `train.py`)
  prints and saves `runs/reports/<run>_<split>.md/.json` with precision, recall,
  AP, how often each class is *missed* (seen as background), what it is confused
  with and where to improve. Read it before the global mAP, which hides weak classes.
- **Using a new model:** the API loads the newest `bugsight_yolov8n_v2` weights if
  they exist, otherwise set `BUGSIGHT_WEIGHTS`. `/api/metrics` reads the
  `results.csv` next to the loaded weights.
- Colour augmentation (`hsv_h`) and mixup/erasing are off on purpose: colour is the
  signal for `color_corruption`, and blending or erasing paints fake defects.

## Configuration

Environment variables (see `.env.example`):

| Variable | Default | Purpose |
| --- | --- | --- |
| `JWT_SECRET` | placeholder | Token signing key. **Required in production** (`FLASK_ENV=production` refuses to start with the placeholder). |
| `JWT_ACCESS_EXPIRES_MIN` / `JWT_REFRESH_EXPIRES_DAYS` | 60 / 30 | Token lifetimes. |
| `DATABASE_URL` | `sqlite:///bugsight.db` | SQLAlchemy URL. |
| `BUGSIGHT_WEIGHTS` | newest `runs/.../best.pt` | Model weights. |
| `BUGSIGHT_ADMIN_EMAIL` / `BUGSIGHT_ADMIN_PASSWORD` | `admin@bugsight.io` / random | Initial admin. |
| `BUGSIGHT_MAX_UPLOAD_MB` | 200 | Upload size limit (images and videos). |
| `BUGSIGHT_CORS_ORIGINS` | `*` | Comma-separated allowed origins. |
| `BUGSIGHT_WARMUP` | 1 | Set to `0` to skip loading the model at startup. |

## Docker

```bash
echo "JWT_SECRET=$(python -c 'import secrets; print(secrets.token_hex(32))')" >> .env
docker compose up --build        # dashboard on http://localhost:8085
```

`docker compose` fails fast if `JWT_SECRET` is missing. The SQLite database lives
in the `bugsight-db` volume, so analyses survive restarts. Check the API log for
the generated admin password on first start.

## API

All routes are under `/api`. Routes marked * need `Authorization: Bearer <token>`.

| Route | Description |
| --- | --- |
| `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`* | Accounts and tokens. |
| `POST /predict`* | Form field `image` (+ `confidence`). Returns detections. |
| `POST /predict-video`* | Form fields `video`, `confidence`, `max_frames` (1-300). |
| `GET /history`* | Query: `limit`, `offset`, `q`, `status` (bug/clean), `type` (image/video). Returns `predictions` and `total`. |
| `DELETE /history/<id>`* | Delete one of your analyses. |
| `GET /stats`* | Your aggregated statistics. |
| `GET /report`* | PDF. Query: `lang` (`en`/`fr`), `include_video=true`. |
| `GET /metrics`, `GET /health` | Model quality, liveness (503 when the database is down). |
| `GET /admin/*`* | Admin only: overview, users, role changes, analyses, system. |

Uploads are limited by size and extension (images: jpg, png, bmp, webp; videos:
mp4, avi, mov, mkv, webm).

## Development

```bash
make test         # pytest
make lint         # ruff check + format check
make check-i18n   # EN/FR translation keys must match
make ci           # all of the above
```

Translations live in `frontend/src/locales/en.js` and `fr.js`; add a key to both
and use it with `t('your.key')`. The PDF report texts are in
`src/api/report_generator.py`.

## Tech stack

YOLOv8 (Ultralytics) - Flask, SQLAlchemy, Flask-JWT-Extended, Gunicorn - React,
Vite, Tailwind CSS, Recharts - Docker, GitHub Actions.

More detail: [docs/architecture.md](docs/architecture.md).
