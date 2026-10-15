# syntax=docker/dockerfile:1
FROM python:3.11-slim-trixie AS builder

ARG UV_VERSION=0.5.29
ENV UV_NO_CACHE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

RUN apt-get update && \
    apt-get upgrade -y && \
    rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir "uv==${UV_VERSION}"
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
COPY scripts ./scripts
RUN uv sync --frozen --no-dev
RUN pip install --no-cache-dir --upgrade "setuptools>=80.0.0"
RUN find /app/.venv /usr/local/lib/python3.11/site-packages -name "*.cdx.json" -delete 2>/dev/null || true
FROM python:3.11-slim-trixie AS runtime

RUN apt-get update && \
    apt-get upgrade -y && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

ARG LOCAL_UID=1000
ARG LOCAL_GID=1000
RUN test "$LOCAL_UID" -gt 0 && test "$LOCAL_GID" -gt 0 && \
    groupadd --gid "$LOCAL_GID" app && useradd --uid "$LOCAL_UID" --gid app --create-home app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
RUN pip install --no-cache-dir --upgrade "setuptools>=80.0.0"
RUN find /app /usr/local/lib/python3.11/site-packages -name "*.cdx.json" -delete 2>/dev/null || true

RUN mkdir /app/reports /app/mutants /app/backups && chown app:app /app/reports /app/mutants /app/backups
USER app
EXPOSE 8000
STOPSIGNAL SIGTERM
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "30"]

FROM node:24.21.0-bookworm-slim AS frontend-base

WORKDIR /app/frontend
RUN npm install --global pnpm@11.19.0
ARG LOCAL_UID=1000
ARG LOCAL_GID=1000
RUN test "$LOCAL_UID" -gt 0 && test "$LOCAL_GID" -gt 0 && \
    groupmod -g "$LOCAL_GID" node && usermod -u "$LOCAL_UID" -g "$LOCAL_GID" node && \
    mkdir -p /pnpm/store && chown node:node /pnpm /pnpm/store /app /app/frontend /home/node
ENV HOME=/home/node
USER node

FROM frontend-base AS frontend

COPY --chown=node:node frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
# Copy source paths explicitly: Windows pnpm links in node_modules may be unreadable.
COPY --chown=node:node frontend/src ./src
COPY --chown=node:node frontend/index.html frontend/vite.config.ts frontend/tsconfig.json frontend/tsconfig.app.json frontend/tsconfig.node.json ./
COPY --chown=node:node frontend/eslint.config.js frontend/prettier.config.mjs frontend/.prettierignore frontend/.gitignore frontend/README.md ./
USER node
EXPOSE 5173
STOPSIGNAL SIGTERM
CMD ["node", "node_modules/vite/bin/vite.js", "--host", "0.0.0.0", "--port", "5173"]

FROM frontend-base AS frontend-test

COPY --chown=node:node frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
# Copy source paths explicitly: Windows pnpm links in node_modules may be unreadable.
COPY --chown=node:node frontend/src ./src
COPY --chown=node:node frontend/index.html frontend/vite.config.ts frontend/tsconfig.json frontend/tsconfig.app.json frontend/tsconfig.node.json ./
COPY --chown=node:node frontend/eslint.config.js frontend/prettier.config.mjs frontend/.prettierignore frontend/.gitignore frontend/README.md ./

COPY scripts/localize_test_output.mjs /scripts/localize_test_output.mjs
USER node
CMD ["sh", "-lc", "node /scripts/localize_test_output.mjs -- pnpm install --frozen-lockfile --prefer-offline --store-dir /pnpm/store && node /scripts/localize_test_output.mjs -- pnpm test:run"]

FROM builder AS test-builder

COPY Makefile ./
COPY tests ./tests
RUN uv sync --frozen --extra dev
RUN find /app/.venv /usr/local/lib/python3.11/site-packages -name "*.cdx.json" -delete 2>/dev/null || true

FROM runtime AS test

USER root
RUN apt-get update && apt-get install -y --no-install-recommends make && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/bin/uv /usr/local/bin/uv
COPY --from=test-builder --chown=app:app /app/.venv /app/.venv
RUN find /app -name "*.cdx.json" -delete 2>/dev/null || true
COPY --from=test-builder --chown=app:app /app/Makefile /app/Makefile
COPY --from=test-builder --chown=app:app /app/tests /app/tests
USER app
