FROM ghcr.io/astral-sh/uv:0.9.5 AS uv

FROM python:3.12-slim-trixie@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30 AS backend
# Менять дату при плановом обновлении пакетов, чтобы сбросить кеш этого слоя.
ARG OS_SECURITY_REFRESH=2026-11-02
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 PATH="/app/.venv/bin:$PATH"
COPY backend/pyproject.toml backend/uv.lock ./
ENV UV_CACHE_DIR=/root/.cache/uv UV_LINK_MODE=copy
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked uv sync --locked --no-dev --no-install-project
COPY backend/app ./app
RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked uv sync --locked --no-dev
RUN useradd --create-home app
COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "30"]

FROM node:24.21.0-bookworm-slim AS frontend
WORKDIR /app
RUN npm install --global pnpm@11.19.0
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm config set store-dir /pnpm/store
RUN --mount=type=cache,target=/pnpm/store,sharing=locked pnpm install --frozen-lockfile && chown -R node:node /app
COPY --chown=node:node frontend/eslint.config.js frontend/prettier.config.mjs frontend/.prettierignore ./
COPY --chown=node:node frontend/index.html frontend/vite.config.ts frontend/tsconfig.json frontend/tsconfig.app.json frontend/tsconfig.node.json ./
COPY --chown=node:node frontend/src ./src
USER node
CMD ["pnpm", "dev", "--host", "0.0.0.0", "--port", "5173", "--strictPort"]
