# Multi-stage build (master prompt 14.1): non-root, healthcheck,
# no secrets in layers, single image for web and worker.

FROM python:3.13-slim AS builder

WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# pinned dependencies first (reproducible builds, better layer caching)
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps .

FROM python:3.13-slim AS runtime

# EPUBCheck (pinned, master prompt 14.1/7.6): JRE + jar in the worker image
ARG EPUBCHECK_VERSION=5.2.1
ADD https://github.com/w3c/epubcheck/releases/download/v${EPUBCHECK_VERSION}/epubcheck-${EPUBCHECK_VERSION}.zip /tmp/epubcheck.zip
RUN apt-get update \
    && apt-get install -y --no-install-recommends default-jre-headless unzip \
    && rm -rf /var/lib/apt/lists/* \
    && unzip -q /tmp/epubcheck.zip -d /opt \
    && mv /opt/epubcheck-${EPUBCHECK_VERSION} /opt/epubcheck \
    && rm /tmp/epubcheck.zip
ENV LIBRARY_EPUBCHECK_JAR=/opt/epubcheck/epubcheck.jar

RUN groupadd -r app && useradd -r -g app -d /app -s /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    LIBRARY_STORAGE_ROOT=/data/storage

WORKDIR /app
RUN mkdir -p /data/storage && chown -R app:app /data /app
USER app

# default: web; worker overrides the command
CMD ["uvicorn", "portal.web.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8001"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8001/healthz', timeout=3).status == 200 else 1)"
