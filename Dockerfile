# syntax=docker/dockerfile:1
FROM python:3.11.11-slim AS builder

ARG UV_VERSION=0.5.29
ENV UV_NO_CACHE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app
RUN python -m pip install --no-cache-dir "uv==${UV_VERSION}"
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

FROM python:3.11.11-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN groupadd --system app && useradd --system --gid app --create-home app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
RUN mkdir /app/reports /app/mutants && chown app:app /app/reports /app/mutants
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM builder AS test-builder

COPY tests ./tests
RUN uv sync --frozen --extra dev

FROM runtime AS test

USER root
COPY --from=test-builder --chown=app:app /app/.venv /app/.venv
COPY --from=test-builder --chown=app:app /app/tests /app/tests
USER app
