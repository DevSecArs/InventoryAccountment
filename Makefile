SHELL := /bin/sh
MAKEFLAGS += --no-print-directory

# Рабочие данные и проверки имеют разные Compose-проекты и тома.
PROJECT_NAME ?= inventory-compose
TEST_RUN_ID ?= $(shell printf '%s' "$(CURDIR)" | cksum | awk '{print $$1}')
TEST_PROJECT := inventory-check-$(TEST_RUN_ID)
# Передаём путь через окружение, а не подставляем его в shell-код рецептов.
override ENV_FILE := $(value ENV_FILE)
export ENV_FILE
COMPOSE := sh scripts/compose.sh --project-name $(PROJECT_NAME) -f docker-compose.yaml
TEST_COMPOSE := docker compose --env-file compose.test.env --project-name $(TEST_PROJECT) -f compose.test.yaml
FRONTEND_TEST_IMAGE ?= inventory-accountment-frontend-test:local
PNPM_STORE_VOLUME ?= inventory-accountment-pnpm-store
BASE_REF ?= main
BACKUP ?=
TARGET_DATABASE ?=
TARGET_DATABASE_URL ?=
CONFIRM_TARGET_DATABASE ?=
RESTORE_EXISTING ?= 0

ifneq ($(filter DOCKER LOCAL TEST,$(.VARIABLES)),)
$(error Флаги DOCKER/LOCAL/TEST удалены. Все команды работают в Docker; проверки изолированы автоматически)
endif

.PHONY: setup run up down status migrate backup restore test test-in-container quality verify test-clean check-test-environment check-test-project-clean frontend-test-image ensure-pnpm-store mutation migration-check backup-restore-check container-smoke lock-check secret-scan image-scan check-working-tree-diff check-branch-diff

setup:
	@docker info >/dev/null
	@docker compose version
	@$(COMPOSE) config --quiet
	@$(COMPOSE) build app frontend

run: up

up:
	@$(COMPOSE) up --build --detach --wait

down:
	@$(COMPOSE) down --remove-orphans

status:
	@$(COMPOSE) ps --all
	@$(COMPOSE) logs --tail 50

migrate:
	@$(COMPOSE) run --rm migrate

check-test-environment:
	@test -n "$(TEST_RUN_ID)" || (echo "TEST_RUN_ID не должен быть пустым" >&2; exit 2)
	@test "$(TEST_PROJECT)" != "$(PROJECT_NAME)" || (echo "Тестовый и рабочий проекты должны различаться" >&2; exit 2)
	@$(TEST_COMPOSE) config --quiet

# Удаляет только ресурсы проверок. make down сохраняет рабочий том.
test-clean: check-test-environment
	@$(TEST_COMPOSE) down --volumes --remove-orphans

test:
	@echo '==> Тесты: запускаю изолированный Docker-контур'
	@$(MAKE) test-in-container TEST_RUN_ID="$(TEST_RUN_ID)"

test-in-container:
	@$(MAKE) check-test-environment
	@echo '==> Backend: собираю актуальный test-образ'
	@$(TEST_COMPOSE) build --progress=plain app
	@echo '==> Backend: применяю миграции к тестовой БД'
	@$(TEST_COMPOSE) run --rm --user root app alembic upgrade head
	@echo '==> Backend: запускаю pytest и проверку покрытия'
	@$(TEST_COMPOSE) run --rm --user root app python scripts/localize_test_output.py -- pytest
	@echo '==> Frontend: подготавливаю test-образ и кэш pnpm'
	@$(MAKE) frontend-test-image
	@$(MAKE) ensure-pnpm-store
	@echo '==> Frontend: запускаю тесты из проектного образа'
	@docker run --rm -v "$(PNPM_STORE_VOLUME):/pnpm/store" "$(FRONTEND_TEST_IMAGE)" sh -lc 'node /scripts/localize_test_output.mjs -- pnpm install --frozen-lockfile --prefer-offline --store-dir /pnpm/store && node /scripts/localize_test_output.mjs -- pnpm test:run'

frontend-test-image:
	@echo '==> Frontend: собираю образ $(FRONTEND_TEST_IMAGE)'
	@docker build --progress=plain --target frontend-test --tag "$(FRONTEND_TEST_IMAGE)" .

ensure-pnpm-store:
	@set -eu; \
	if docker volume inspect "$(PNPM_STORE_VOLUME)" >/dev/null 2>&1; then \
		echo '==> Frontend: использую существующий pnpm-кэш $(PNPM_STORE_VOLUME)'; \
	else \
		echo '==> Frontend: создаю pnpm-кэш $(PNPM_STORE_VOLUME)'; \
		docker volume create "$(PNPM_STORE_VOLUME)" >/dev/null; \
	fi

quality:
	@$(MAKE) check-test-environment
	@echo '==> Backend: собираю актуальный test-образ для статических проверок'
	@$(TEST_COMPOSE) build --progress=plain app
	@echo '==> Backend: запускаю Ruff и mypy без зависимостей Compose'
	@$(TEST_COMPOSE) run --rm --no-deps --user root app sh -c 'mkdir -p reports && echo "==> Ruff: проверка форматирования" && ruff format --check --no-cache app tests scripts && echo "==> Ruff: статический анализ" && ruff check --no-cache app tests scripts && echo "==> mypy: проверка типов" && MYPY_CACHE_DIR=/tmp/mypy mypy app tests scripts'
	@echo '==> SAST: начинаю статический анализ безопасности; тип — Bandit'
	@set +e; \
	if $(TEST_COMPOSE) run --rm --no-deps --user root app bandit -q -r app scripts -lll -f json -o reports/bandit.json; then sast_status=0; else sast_status=$$?; fi; \
	if $(TEST_COMPOSE) run --rm --no-deps --user root app python scripts/summarize_bandit.py reports/bandit.json "$$sast_status"; then summary_status=0; else summary_status=$$?; fi; \
	if [ "$$sast_status" -ne 0 ]; then exit "$$sast_status"; fi; \
	exit "$$summary_status"
	@echo '==> Backend: запускаю audit Python-зависимостей без зависимостей Compose'
	@$(TEST_COMPOSE) run --rm --no-deps --user root app sh -c 'pip freeze --exclude-editable > /tmp/requirements.txt && pip-audit --strict --format json -o reports/pip-audit.json -r /tmp/requirements.txt'
	@mkdir -p reports
	@echo '==> Frontend: подготавливаю образ и pnpm-кэш для проверок качества'
	@$(MAKE) frontend-test-image
	@$(MAKE) ensure-pnpm-store
	@echo '==> Frontend: запускаю форматирование, lint, typecheck и audit'
	@docker run --rm -v "$(PNPM_STORE_VOLUME):/pnpm/store" -v "$(CURDIR)/reports:/reports" "$(FRONTEND_TEST_IMAGE)" sh -lc 'pnpm install --frozen-lockfile --prefer-offline --store-dir /pnpm/store && pnpm quality && pnpm audit --audit-level=high --json > /reports/pnpm-audit.json'
	@$(MAKE) secret-scan

secret-scan:
	@mkdir -p reports
	@docker run --rm -v "$(CURDIR):/repo:ro" -v "$(CURDIR)/reports:/reports" zricethezav/gitleaks:v8.21.2 detect --source=/repo --report-format=json --report-path=/reports/gitleaks.json --redact --exit-code=1

image-scan:
	@test -n "$(IMAGE_ID)" || (echo "Укажите IMAGE_ID собранного образа" >&2; exit 2)
	@mkdir -p reports
	@docker image inspect "$(IMAGE_ID)" --format '{{.Id}}' >/dev/null
	@docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$(CURDIR)/reports:/reports" aquasec/trivy:0.56.2 image --severity HIGH,CRITICAL --exit-code 1 --ignore-unfixed --format json --output /reports/trivy-image.json "$(IMAGE_ID)"

mutation:
	@$(MAKE) check-test-environment
	@$(TEST_COMPOSE) run --rm app alembic upgrade head
	@$(TEST_COMPOSE) run --rm -e PYTEST_ADDOPTS=--no-cov app python scripts/check_critical_mutations.py

migration-check:
	@$(MAKE) check-test-environment
	@$(TEST_COMPOSE) run --rm app python scripts/migration_check.py

backup:
	@$(COMPOSE) run --rm pg-tools sh /scripts/backup_restore.sh backup /backups

restore:
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
	@$(MAKE) check-test-environment
	@$(TEST_COMPOSE) run --rm app alembic upgrade head
	@$(TEST_COMPOSE) run --rm pg-tools sh /scripts/backup_restore_check.sh /backups

lock-check:
	@echo '==> Lock-файлы: проверяю Python-зависимости'
	@$(TEST_COMPOSE) build app
	@$(TEST_COMPOSE) run --rm --no-deps --user root app uv lock --check
	@echo '==> Lock-файлы: подготавливаю frontend-образ и pnpm-кэш'
	@$(MAKE) frontend-test-image
	@$(MAKE) ensure-pnpm-store
	@echo '==> Lock-файлы: проверяю frontend-зависимости'
	@docker run --rm -v "$(PNPM_STORE_VOLUME):/pnpm/store" "$(FRONTEND_TEST_IMAGE)" pnpm install --frozen-lockfile --prefer-offline --store-dir /pnpm/store

container-smoke:
	@$(MAKE) check-test-environment
	@set -eu; \
	cleanup() { $(TEST_COMPOSE) down --volumes --remove-orphans; }; \
	trap cleanup EXIT HUP INT TERM; \
	$(TEST_COMPOSE) up --build --detach --wait; \
	image_id=$$(docker inspect --format '{{.Image}}' "$$($(TEST_COMPOSE) ps -q app)"); \
	$(MAKE) image-scan IMAGE_ID="$$image_id"; \
	$(TEST_COMPOSE) run --rm app alembic upgrade head; \
	$(TEST_COMPOSE) exec -T app python scripts/container_smoke.py; \
	$(TEST_COMPOSE) ps; \
	cleanup; \
	trap - EXIT HUP INT TERM

check-test-project-clean:
	@$(MAKE) check-test-environment TEST_RUN_ID="$(TEST_RUN_ID)"
	@test -z "$$($(TEST_COMPOSE) ps --all --quiet)" || (echo "Остались контейнеры тестового Compose-проекта" >&2; exit 2)
	@test -z "$$(docker volume ls --filter label=com.docker.compose.project=$(TEST_PROJECT) --quiet)" || (echo "Остались тома тестового Compose-проекта" >&2; exit 2)

check-working-tree-diff:
	@git diff --check

check-branch-diff:
	@base=$$(git merge-base HEAD "$(BASE_REF)") || (echo "Не удалось определить merge-base с $(BASE_REF)" >&2; exit 2); \
	git diff --check "$$base...HEAD"

verify:
	@set -eu; \
	cleanup() { echo '==> Очистка изолированного тестового Compose-проекта; pnpm-кэш $(PNPM_STORE_VOLUME) сохраняется'; $(MAKE) test-clean TEST_RUN_ID="$(TEST_RUN_ID)"; }; \
	trap cleanup EXIT HUP INT TERM; \
	echo '==> Подготовка изолированного Docker-контура'; $(MAKE) check-test-environment TEST_RUN_ID="$(TEST_RUN_ID)"; \
	echo '==> Проверка lock-файлов'; $(MAKE) lock-check TEST_RUN_ID="$(TEST_RUN_ID)"; \
	echo '==> Проверка качества, включая SAST Bandit'; $(MAKE) quality TEST_RUN_ID="$(TEST_RUN_ID)"; \
	echo '==> Автоматические тесты'; $(MAKE) test TEST_RUN_ID="$(TEST_RUN_ID)"; \
	echo '==> Мутационная проверка'; $(MAKE) mutation TEST_RUN_ID="$(TEST_RUN_ID)"; \
	echo '==> Проверка миграций'; $(MAKE) migration-check TEST_RUN_ID="$(TEST_RUN_ID)"; \
	echo '==> Проверка backup/restore'; $(MAKE) backup-restore-check TEST_RUN_ID="$(TEST_RUN_ID)"; \
	echo '==> Контейнерный smoke-сценарий'; $(MAKE) container-smoke TEST_RUN_ID="$(TEST_RUN_ID)"; \
	echo '==> Проверка очистки тестового проекта'; $(MAKE) check-test-project-clean TEST_RUN_ID="$(TEST_RUN_ID)"; \
	echo '==> Проверка whitespace рабочей копии'; $(MAKE) check-working-tree-diff; \
	echo '==> Проверка whitespace веточной разницы'; $(MAKE) check-branch-diff; \
	cleanup; \
	trap - EXIT HUP INT TERM
	@echo '==> Проверки успешно завершены; приложение автоматически не запускается'
