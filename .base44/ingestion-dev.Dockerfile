# Dependency-only image for the Python ingestion services in local dev.
# It installs the runtime dependencies that workers/ingestion-python/pyproject.toml
# declares (mirror of workers/ingestion-python/Dockerfile), and deliberately does
# NOT copy application source: the repository is bind-mounted at /app so the
# running service always executes the current checkout.
FROM python:3.14-slim

ENV PYTHONPATH=/app/workers/ingestion-python/src:/app/packages/contracts/python \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "minio>=7.2,<8" \
    "nats-py>=2.9,<3" \
    "Pillow>=11,<13" \
    "pdf2image>=1.17,<2" \
    "pypdf>=5,<6" \
    "psycopg[binary]>=3.2,<4" \
    "pytesseract>=0.3,<0.4" \
    "reportlab>=4.2,<5"

WORKDIR /app
