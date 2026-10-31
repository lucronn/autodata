# Base44 development image for the Python ingestion worker / HTTP adapter.
# Installs runtime dependencies only; the repository is bind-mounted at
# /workspace by docker-compose.base44.yml.
FROM python:3.14-slim

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

ENV PYTHONPATH=/workspace/workers/ingestion-python/src:/workspace/packages/contracts/python
ENV PYTHONUNBUFFERED=1
WORKDIR /workspace
CMD ["python", "-m", "autodata_ingestion.worker"]
