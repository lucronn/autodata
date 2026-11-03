FROM python:3.14-slim
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr && rm -rf /var/lib/apt/lists/*
COPY workers/ingestion-python/pyproject.toml /tmp/pyproject.toml
RUN python -c "import tomllib,subprocess; p=tomllib.load(open('/tmp/pyproject.toml','rb')); subprocess.check_call(['pip','install','--no-cache-dir',*p['project']['dependencies'],'pytest>=8,<10'])"
