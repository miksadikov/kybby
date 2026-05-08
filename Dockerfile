# syntax=docker/dockerfile:1

FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    DEBUG=false \
    DATA_DIR=/data/data \
    OUTPUT_DIR=/data/out

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        build-essential \
        libgl1 \
        libglib2.0-0 \
        gosu \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY providers ./providers
COPY ./.env.example ./
COPY frontend ./frontend
COPY --from=frontend-build /build/frontend/dist ./frontend/dist
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

RUN set -eux; \
    for req in \
        providers/brandkit_recraft/requirements.txt \
        providers/brandkit_seedream/requirements.txt \
        providers/brandkit_flux2/requirements.txt; do \
        if [ -f "$req" ]; then pip install -r "$req"; fi; \
    done; \
    mkdir -p /data/data /data/out; \
    useradd --create-home --shell /bin/bash appuser; \
    chown -R appuser:appuser /app /data; \
    chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["sh", "-c", "uvicorn app.main:app --host ${APP_HOST:-0.0.0.0} --port ${APP_PORT:-8000}"]
