# Backend container — used for all three workers + Flask main process.
# Keep the image slim; CUDA/torch GPU base is reserved for M1 once we wire the
# real YOLO inference path. For M0 the consumer falls back to the stub when
# ultralytics is missing, which is fine for the skeleton.

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
  && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
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

COPY app ./app
COPY README.md ./

EXPOSE 8000 9101 9102 9103
CMD ["python", "-m", "app.api"]
