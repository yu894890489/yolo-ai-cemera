# Multi-stage backend image (BE-M1-D / YU-56).
#
# Build context is the REPO ROOT (see docker-compose.yml) so the frontend can be
# built and its dist baked into the image — no separate `pnpm preview` needed.
#
#   stage 1 (frontend-build): node -> Vite build -> /build/app/static/frontend
#   stage 2 (base):           python slim, CPU stub YOLO (default)
#
# The GPU/ultralytics consumer is a separate image (docker/Dockerfile.gpu),
# opted into via docker-compose.gpu.yml. The CPU stub path stays the default.

# ---------- stage 1: frontend ----------
FROM node:20-slim AS frontend-build
WORKDIR /build
RUN corepack enable
COPY frontend/ ./frontend/
WORKDIR /build/frontend
RUN pnpm install --frozen-lockfile
# Vite outDir resolves to /build/app/static/frontend (see frontend/vite.config.ts).
RUN pnpm build

# ---------- stage 2: python runtime ----------
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
  && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml ./
RUN pip install --upgrade pip \
 && pip install \
      "flask>=3.0,<4.0" \
      "flask-sock>=0.7" \
      "redis>=5.0,<6.0" \
      "prometheus-client>=0.20" \
      "pymysql>=1.1" \
      "minio>=7.2" \
      "pyyaml>=6.0" \
      "opencv-python-headless>=4.9" \
      "numpy>=1.26"

COPY backend/app ./app
COPY backend/sql ./sql
COPY backend/README.md ./

# Bake the built frontend into the image so Flask can serve it at /static/frontend.
COPY --from=frontend-build /build/app/static/frontend ./app/static/frontend

EXPOSE 8010 9101 9102 9103
CMD ["python", "-m", "app.api"]
