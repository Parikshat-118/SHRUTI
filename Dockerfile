# SHRUTI - one image, five deployment targets.
#
# The same artefact serves every tier of the deployment ladder:
#   T1  Hugging Face Spaces (Docker SDK, free CPU tier)
#   T2  Google Cloud Run    (scale-to-zero, free tier at light traffic)
#   T4  offline installer   (`docker save` -> USB stick -> `docker load`)
#
# Build-time network is fine; RUNTIME network is not required for anything.
# No licence check, no model download, no telemetry, no update ping.  The
# no-egress CI job proves that rather than asserting it.

# ---------------------------------------------------------------- frontend ---
FROM node:24-alpine AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci --no-fund --no-audit
COPY frontend/ ./
# Vite emits into shruti/web/static; everything is bundled locally, so the
# running container never fetches an asset from a CDN.
RUN npm run build && ls -la /build/../shruti/web/static 2>/dev/null || true

# ----------------------------------------------------------------- runtime ---
FROM python:3.13-slim AS runtime

LABEL org.opencontainers.image.title="SHRUTI" \
      org.opencontainers.image.description="Blind RF signal exploitation: samples to bits" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.source="https://github.com/Parikshat-118/SHRUTI"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=7860

WORKDIR /app

COPY pyproject.toml README.md ./
COPY shruti/ ./shruti/
COPY cartridges/ ./cartridges/
COPY --from=frontend /shruti/web/static ./shruti/web/static

RUN pip install --no-cache-dir ".[gui]" \
 && python -c "from shruti.cartridge import load_library; l=load_library(); assert not l.errors, l.errors; print('cartridges:', l.summary())"

# Non-root: a security reviewer looks for this, and it costs nothing.
RUN useradd -m -u 1000 shruti && chown -R shruti:shruti /app
USER shruti

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",7860)}/api/health').read()"

# Hugging Face Spaces and Cloud Run both inject $PORT.
CMD ["sh", "-c", "uvicorn shruti.web.app:app --host 0.0.0.0 --port ${PORT:-7860} --log-level warning"]
