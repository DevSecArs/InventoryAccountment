SHELL := /bin/sh

TEST ?= 0
UV_VERSION := 0.5.29
BACKUP ?=
TARGET_DATABASE ?=
TARGET_DATABASE_URL ?=
CONFIRM_TARGET_DATABASE ?=
RESTORE_EXISTING ?= 0

ifeq ($(TEST),1)
ENV_FILE := .env.test
COMPOSE := docker compose --project-name inventory-accountment-test --env-file $(ENV_FILE) -f compose.test.yaml
else
ENV_FILE := .env
COMPOSE := docker compose --project-name inventory-accountment --env-file $(ENV_FILE) -f docker-compose.yaml
endif

.PHONY: setup run up down migrate test quality mutation migration-check backup restore backup-restore-check lock-check container-check verify check-test-environment check-test-project-clean

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
	@$(COMPOSE) run --rm app sh -c 'mkdir -p reports && ruff format --check --no-cache app tests scripts && ruff check --no-cache app tests scripts && MYPY_CACHE_DIR=/tmp/mypy mypy app tests scripts && bandit -q -r app scripts -lll -f json -o reports/bandit.json && pip freeze --exclude-editable > /tmp/requirements.txt && pip-audit --strict --format json -o reports/pip-audit.json -r /tmp/requirements.txt'
else
	@uv run --frozen ruff format --check --no-cache app tests scripts
	@uv run --frozen ruff check --no-cache app tests scripts
	@MYPY_CACHE_DIR=/tmp/mypy uv run --frozen mypy app tests scripts
	@mkdir -p reports
	@uv run --frozen bandit -q -r app scripts -lll -f json -o reports/bandit.json
	@uv run --frozen sh -c 'pip freeze --exclude-editable > /tmp/requirements.txt && pip-audit --strict --format json -o reports/pip-audit.json -r /tmp/requirements.txt'
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

backup:
ifeq ($(TEST),1)
	@$(MAKE) check-test-environment TEST=1
endif
	@$(COMPOSE) run --rm pg-tools sh /scripts/backup_restore.sh backup /backups

restore:
ifeq ($(TEST),1)
	@$(MAKE) check-test-environment TEST=1
endif
	@test -n "$(BACKUP)" || (echo "Укажите BACKUP=backups/<имя>.dump" >&2; exit 2)
	@case "$(BACKUP)" in backups/*.dump) ;; *) echo "BACKUP должен указывать на дамп в backups/" >&2; exit 2 ;; esac
	@backup_name=$$(basename "$(BACKUP)"); \
	$(COMPOSE) run --rm \
		-e BACKUP_FILE="/backups/$$backup_name" \
		-e TARGET_DATABASE="$(TARGET_DATABASE)" \
		-e TARGET_DATABASE_URL="$(TARGET_DATABASE_URL)" \
		-e CONFIRM_TARGET_DATABASE="$(CONFIRM_TARGET_DATABASE)" \
		-e RESTORE_EXISTING="$(RESTORE_EXISTING)" \
		pg-tools sh /scripts/backup_restore.sh restore

backup-restore-check:
ifeq ($(TEST),1)
	@$(MAKE) check-test-environment TEST=1
	@$(COMPOSE) run --rm pg-tools sh /scripts/backup_restore_check.sh /backups
else
	@echo "Проверка backup/restore разрешена только с TEST=1" >&2
	@exit 2
endif

lock-check:
	@uv lock --check
	@docker run --rm -v "$(CURDIR)/frontend:/src:ro" node:24.21.0-bookworm-slim sh -lc 'mkdir /work && tar --exclude=node_modules -C /src -cf - . | tar -C /work -xf - && cd /work && npm install --global pnpm@11.19.0 && pnpm install --frozen-lockfile'

container-check:
ifeq ($(TEST),1)
	@$(MAKE) check-test-environment TEST=1
	@set -eu; \
	cleanup() { $(COMPOSE) down --volumes --remove-orphans; }; \
	trap cleanup EXIT HUP INT TERM; \
	$(COMPOSE) up --build --detach --wait; \
	$(COMPOSE) run --rm app alembic upgrade head; \
	$(COMPOSE) exec -T app python scripts/container_smoke.py; \
	$(COMPOSE) ps; \
	cleanup; \
	trap - EXIT HUP INT TERM
else
	@echo "Контейнерная проверка разрешена только с TEST=1" >&2
	@exit 2
endif

check-test-project-clean:
	@$(MAKE) check-test-environment TEST=1
	@test -z "$$($(COMPOSE) ps --all --quiet)" || (echo "Остались контейнеры тестового Compose-проекта" >&2; exit 2)
	@test -z "$$(docker volume ls --filter label=com.docker.compose.project=inventory-accountment-test --quiet)" || (echo "Остались тома тестового Compose-проекта" >&2; exit 2)

verify:
ifeq ($(TEST),1)
	@$(MAKE) check-test-environment TEST=1
	@set -eu; \
	cleanup() { $(COMPOSE) down --volumes --remove-orphans; }; \
	trap cleanup EXIT HUP INT TERM; \
	echo '==> Проверка lock-файлов'; $(MAKE) lock-check TEST=1; \
	echo '==> Проверка качества'; $(MAKE) quality TEST=1; \
	echo '==> Автоматические тесты'; $(MAKE) test TEST=1; \
	echo '==> Мутационная проверка'; $(MAKE) mutation TEST=1; \
	echo '==> Проверка миграций'; $(MAKE) migration-check TEST=1; \
	echo '==> Проверка backup/restore'; $(MAKE) backup-restore-check TEST=1; \
	echo '==> Контейнерный smoke-сценарий'; $(MAKE) container-check TEST=1; \
	echo '==> Проверка очистки тестового проекта'; $(MAKE) check-test-project-clean TEST=1; \
	echo '==> Проверка формата Git diff'; git diff --check; \
	trap - EXIT HUP INT TERM
else
	@echo "Полный контур verify разрешён только с TEST=1" >&2
	@exit 2
endif
