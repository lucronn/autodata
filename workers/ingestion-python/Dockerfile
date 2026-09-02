FROM python:3.14-slim

WORKDIR /app
COPY workers/ingestion-python/pyproject.toml ./
RUN pip install --no-cache-dir "minio>=7.2,<8" "nats-py>=2.9,<3" "psycopg[binary]>=3.2,<4"
COPY workers/ingestion-python/src ./src
COPY packages/contracts/python ./contracts
COPY scripts/dev/ingestion_smoke.py ./scripts/ingestion_smoke.py
ENV PYTHONPATH=/app/src:/app/contracts
CMD ["python", "-m", "autodata_ingestion.worker"]
