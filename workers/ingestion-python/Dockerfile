FROM python:3.14-slim

WORKDIR /app
COPY workers/ingestion-python/pyproject.toml ./
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir "minio>=7.2,<8" "nats-py>=2.9,<3" "Pillow>=11,<13" "pdf2image>=1.17,<2" "pypdf>=5,<6" "psycopg[binary]>=3.2,<4" "pytesseract>=0.3,<0.4"
COPY workers/ingestion-python/src ./src
COPY packages/contracts/python ./contracts
COPY scripts/dev/ingestion_smoke.py ./scripts/ingestion_smoke.py
COPY scripts/dev/normalize_source_directory.py ./scripts/normalize_source_directory.py
COPY scripts/dev/reconcile_payments.py ./scripts/reconcile_payments.py
COPY scripts/dev/operational_metrics.py ./scripts/operational_metrics.py
COPY scripts/dev/nats_health.py ./scripts/nats_health.py
COPY scripts/dev/object_storage_health.py ./scripts/object_storage_health.py
COPY scripts/dev/replay_outbox.py ./scripts/replay_outbox.py
ENV PYTHONPATH=/app/src:/app/contracts
CMD ["python", "-m", "autodata_ingestion.worker"]
