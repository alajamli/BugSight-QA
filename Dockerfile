# BugSight QA - Backend Dockerfile

FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 600 --retries 10 \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir --timeout 600 --retries 10 -r requirements.txt

COPY src/ ./src/
COPY scripts/ ./scripts/
COPY configs/ ./configs/
COPY .env.example .env.example

ENV BUGSIGHT_WEIGHTS=/app/models/best.pt
ENV BUGSIGHT_DATA_YAML=/app/data/processed/data.yaml
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

EXPOSE 5000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/api/health', timeout=3)" || exit 1

# Previously ran the Flask dev server ("Do not use it in a production
# deployment" was printed on every startup) — Gunicorn is the real WSGI
# server. --timeout 120 gives /api/predict-video room to finish; keep worker
# count low since each worker lazily loads its own copy of the YOLO model.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", \
     "--workers", "2", "--threads", "2", "--timeout", "120", \
     "src.api.app:app"]