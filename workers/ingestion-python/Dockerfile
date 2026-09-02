FROM python:3.14-slim

WORKDIR /app
COPY workers/ingestion-python/pyproject.toml ./
COPY workers/ingestion-python/src ./src
ENV PYTHONPATH=/app/src
CMD ["python", "-m", "autodata_ingestion.worker"]
