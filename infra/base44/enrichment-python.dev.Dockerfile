# Base44 development image for the Python enrichment worker / outbox relay.
# Installs runtime dependencies only; the repository is bind-mounted at
# /workspace by docker-compose.base44.yml.
FROM python:3.14-slim

RUN pip install --no-cache-dir \
    "nats-py>=2.9,<3" \
    "psycopg[binary]>=3.2,<4"

ENV PYTHONPATH=/workspace/workers/enrichment-python/src
ENV PYTHONUNBUFFERED=1
WORKDIR /workspace
CMD ["python", "-m", "autodata_enrichment.worker"]
