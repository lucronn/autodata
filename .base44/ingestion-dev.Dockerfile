# Dependency-only image for the Python ingestion services in local dev.
# It installs the runtime dependencies that workers/ingestion-python/pyproject.toml
# declares (mirror of workers/ingestion-python/Dockerfile), and deliberately does
# NOT copy application source: the repository is bind-mounted at /app so the
# running service always executes the current checkout.
FROM python:3.14-slim

ENV PYTHONPATH=/app/workers/ingestion-python/src:/app/packages/contracts/python \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY workers/ingestion-python/pyproject.toml ./pyproject.toml

RUN apt-get update \
    && apt-get install -y --no-install-recommends libcairo2 fonts-dejavu-core poppler-utils tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

RUN python -c "import tomllib,subprocess; p=tomllib.load(open('pyproject.toml','rb')); subprocess.check_call(['pip','install','--no-cache-dir',*p['project']['dependencies']])"
