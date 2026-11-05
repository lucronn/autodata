FROM golang:1.26 AS go-toolchain
FROM python:3.14-slim AS lifecycle-runtime
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr postgresql-client git && rm -rf /var/lib/apt/lists/*
COPY workers/ingestion-python/pyproject.toml /tmp/pyproject.toml
RUN python -c "import tomllib,subprocess; p=tomllib.load(open('/tmp/pyproject.toml','rb')); subprocess.check_call(['pip','install','--no-cache-dir',*p['project']['dependencies'],'pytest>=8,<10'])"

COPY --from=go-toolchain /usr/local/go /usr/local/go
ENV PATH="/usr/local/go/bin:${PATH}"
ENV GOTOOLCHAIN=local CGO_ENABLED=0 GOMODCACHE=/opt/go-module-cache
COPY apps/api-go/go.mod apps/api-go/go.sum /opt/prefetch/apps/api-go/
COPY packages/contracts/go/go.mod /opt/prefetch/packages/contracts/go/
RUN cd /opt/prefetch/apps/api-go && go mod download && go version | grep 'go1.26' && psql --version && pg_dump --version && git --version

# Optional acceptance image; the default image below stays the lifecycle runtime.
FROM lifecycle-runtime AS browser-runtime
COPY scripts/dev/requirements-workshop-browser.txt /tmp/requirements-workshop-browser.txt
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/autodata-playwright
RUN python -m pip install --no-cache-dir -r /tmp/requirements-workshop-browser.txt && python -m playwright install --with-deps chromium firefox webkit

FROM lifecycle-runtime AS default-runtime
