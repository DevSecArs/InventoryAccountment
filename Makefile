SHELL := /bin/sh

TEST ?= 0
UV_VERSION := 0.5.29

ifeq ($(TEST),1)
ENV_FILE := .env.test
COMPOSE := docker compose --project-name inventory-accountment-test --env-file $(ENV_FILE) -f compose.test.yaml
else
ENV_FILE := .env
COMPOSE := docker compose --project-name inventory-accountment --env-file $(ENV_FILE) -f docker-compose.yaml
endif

.PHONY: setup run up down migrate test quality mutation migration-check check-test-environment

setup:
	@python --version
	@docker compose version
	@node --version
	@pnpm --version
	@test -f $(ENV_FILE) || cp $(ENV_FILE).example $(ENV_FILE)
	@python -m pip install --user "uv==$(UV_VERSION)"
	@uv sync --frozen --extra dev
	@pnpm --dir frontend install --frozen-lockfile

check-test-environment:
	@test "$(TEST)" = "1" || (echo "Эта операция разрешена только с TEST=1" >&2; exit 2)
	@test -f .env.test || (echo "Нет .env.test: выполните make setup TEST=1" >&2; exit 2)
	@grep -qx 'APP_ENV=test' .env.test || (echo "APP_ENV в .env.test должен быть test" >&2; exit 2)
	@grep -Eq '^POSTGRES_DB=.*_test$$' .env.test || (echo "Имя тестовой БД должно оканчиваться на _test" >&2; exit 2)

run:
ifeq ($(TEST),1)
	@$(MAKE) check-test-environment TEST=1
	@$(COMPOSE) up --build
else
	@uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port "$${APP_PORT:-8000}"
endif

up:
ifeq ($(TEST),1)
	@$(MAKE) check-test-environment TEST=1
endif
	@$(COMPOSE) up --build --detach --wait

down:
ifeq ($(TEST),1)
	@$(MAKE) check-test-environment TEST=1
	@$(COMPOSE) down --volumes --remove-orphans
else
	@$(COMPOSE) down --remove-orphans
endif

migrate:
ifeq ($(TEST),1)
	@$(MAKE) check-test-environment TEST=1
	@$(COMPOSE) run --rm app alembic upgrade head
else
	@uv run --frozen alembic upgrade head
endif

test:
ifeq ($(TEST),1)
	@$(MAKE) check-test-environment TEST=1
	@$(COMPOSE) run --rm app alembic upgrade head
	@$(COMPOSE) run --rm app pytest
else
	@uv run --frozen pytest
endif
	@docker run --rm -v "$(CURDIR)/frontend:/src:ro" node:24.21.0-bookworm-slim sh -lc 'mkdir /work && tar --exclude=node_modules -C /src -cf - . | tar -C /work -xf - && cd /work && npm install --global pnpm@11.19.0 && pnpm install --frozen-lockfile && pnpm test:run'

quality:
ifeq ($(TEST),1)
	@$(MAKE) check-test-environment TEST=1
	@$(COMPOSE) run --rm app sh -c 'ruff format --check --no-cache app tests scripts && ruff check --no-cache app tests scripts && MYPY_CACHE_DIR=/tmp/mypy mypy app tests scripts && bandit -q -r app scripts -lll && pip freeze --exclude-editable > /tmp/requirements.txt && pip-audit --strict -r /tmp/requirements.txt'
else
	@uv run --frozen ruff format --check --no-cache app tests scripts
	@uv run --frozen ruff check --no-cache app tests scripts
	@MYPY_CACHE_DIR=/tmp/mypy uv run --frozen mypy app tests scripts
	@uv run --frozen bandit -q -r app scripts -lll
	@uv run --frozen sh -c 'pip freeze --exclude-editable > /tmp/requirements.txt && pip-audit --strict -r /tmp/requirements.txt'
endif
	@docker run --rm -v "$(CURDIR)/frontend:/src:ro" node:24.21.0-bookworm-slim sh -lc 'mkdir /work && tar --exclude=node_modules -C /src -cf - . | tar -C /work -xf - && cd /work && npm install --global pnpm@11.19.0 && pnpm install --frozen-lockfile && pnpm quality'

mutation:
ifeq ($(TEST),1)
	@$(MAKE) check-test-environment TEST=1
	@$(COMPOSE) run --rm -e PYTEST_ADDOPTS=--no-cov app mutmut run "*verify_password*"
else
	@echo "Мутационная проверка разрешена только с TEST=1" >&2
	@exit 2
endif

migration-check:
ifeq ($(TEST),1)
	@$(MAKE) check-test-environment TEST=1
	@$(COMPOSE) run --rm app python scripts/migration_check.py
else
	@echo "Проверка миграций разрешена только с TEST=1" >&2
	@exit 2
endif
