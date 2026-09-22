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

.PHONY: setup run up down migrate test check-test-environment

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
