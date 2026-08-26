# Multi-stage build (master prompt 14.1): non-root, healthcheck,
# no secrets in layers, single image for web and worker.

FROM python:3.13-slim AS builder

WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

FROM python:3.13-slim AS runtime

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
