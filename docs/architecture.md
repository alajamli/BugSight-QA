# BugSight QA - Architecture

## Overview

BugSight QA detects six classes of visual rendering bugs (missing texture, texture
glitch, z-fighting, screen tear, UV stretch, color corruption) in game screenshots
and videos using YOLOv8. Three layers: data generation, model training, and a
full-stack web app.

```
React dashboard (Vite)  --/api-->  Flask API (Gunicorn)  -->  YOLOv8 model (in memory)
                                         |
                                         +--> SQLite (users, analyses metadata)
```

## Prediction flow

**Image** (`POST /api/predict`)

1. The dashboard uploads the screenshot with the confidence threshold.
2. Flask validates extension, size and numeric parameters, decodes the image and
   runs inference (guarded by a lock: Ultralytics models are not thread-safe).
3. The detections are stored as metadata (the image itself is not kept) and returned.
4. The frontend draws the boxes on a canvas.

**Video** (`POST /api/predict-video`)

1. The upload is streamed to a temp file (always deleted afterwards).
2. Frames are `grab()`-ed sequentially and only the evenly spaced sample is decoded,
   then inferred in batches of 8 to keep memory flat.
3. The summary and per-frame results are stored with the analysis, per user, so the
   PDF report can include the caller's own latest video.

## Backend modules

| File | Role |
| --- | --- |
| `src/api/app.py` | App factory, routes, validation, rate limiting, model state. |
| `src/api/models.py` | `User` and `Prediction` models, small forward-only migration, first-admin seeding. |
| `src/api/report_generator.py` | PDF report (French and English text tables). |
| `src/model/` | Training config, evaluation, and `report.py` (per-class table: recall, missed rate, confusions, hints). |
| `src/data_generation/` | Scene generator for the six classes; each defect is rendered visibly and verified against the clean scene. |

Security notes: JWT secret is mandatory in production, no default admin password,
login/register are rate limited, uploads are capped and extension-checked,
internal error details are not returned to clients.

## Frontend

- `src/i18n.jsx` + `src/locales/{en,fr}.js`: language context, `t()`, API error
  translation, class names. `npm run check:i18n` guards key parity.
- `src/ToastContext.jsx`: notifications (translated when rendered).
- `src/api.js`: axios client with silent token refresh, upload progress and cancel.
- Chart panels and the admin area are lazy-loaded (Recharts is the heavy part).
- Fonts are self-hosted through `@fontsource`.

## Endpoints

See the table in the [README](../README.md#api).
