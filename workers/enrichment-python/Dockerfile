FROM python:3.14-slim

WORKDIR /app
COPY workers/enrichment-python/pyproject.toml ./
COPY workers/enrichment-python/src ./src
ENV PYTHONPATH=/app/src
CMD ["python", "-m", "autodata_enrichment.worker"]
