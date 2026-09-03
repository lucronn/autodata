FROM python:3.14-slim

WORKDIR /app
COPY workers/enrichment-python/pyproject.toml ./
RUN pip install --no-cache-dir "psycopg[binary]>=3.2,<4"
COPY workers/enrichment-python/src ./src
COPY scripts/dev/deep_lane_smoke.py ./scripts/deep_lane_smoke.py
ENV PYTHONPATH=/app/src
CMD ["python", "-m", "autodata_enrichment.worker"]
