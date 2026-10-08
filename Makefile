SHELL := /bin/sh

DOCKER ?= 0
DOCKER_RUN_ID ?= $(shell printf '%s' "$(CURDIR)" | cksum | awk '{print $$1}')
UV_VERSION := 0.5.29
PYTHON ?= python3
UV := $(PYTHON) -m uv
RUNTIME_DIR := reports/runtime
FRONTEND_TEST_IMAGE ?= inventory-accountment-frontend-test:local
PNPM_STORE_VOLUME ?= inventory-accountment-pnpm-store
PRODUCTION_ENV_FILE ?= /etc/InventoryAccountment/InventoryAccountment.env
BACKUP ?=
BASE_REF ?= main
TARGET_DATABASE ?=
TARGET_DATABASE_URL ?=
CONFIRM_TARGET_DATABASE ?=
RESTORE_EXISTING ?= 0

ifneq ($(filter TEST,$(.VARIABLES)),)
$(error Параметр TEST устарел. Используйте DOCKER=1 для изолированного локального контура)
endif

ifneq ($(filter LOCAL,$(.VARIABLES)),)
$(error Параметр LOCAL переименован. Используйте DOCKER=1 для изолированного Docker-контура)
endif

ifeq ($(DOCKER),1)
ENV_FILE := .env.example
DOCKER_PROJECT := inventory-accountment-local-$(DOCKER_RUN_ID)
COMPOSE := docker compose --project-name $(DOCKER_PROJECT) --env-file $(ENV_FILE) -f compose.test.yaml
else
ENV_FILE := $(PRODUCTION_ENV_FILE)
DOCKER_PROJECT := inventory-accountment
COMPOSE := docker compose --project-name $(DOCKER_PROJECT) --env-file $(ENV_FILE) -f docker-compose.yaml
endif

.PHONY: setup run up down stop-local status migrate test test-in-container frontend-test-image ensure-pnpm-store quality mutation migration-check backup restore backup-restore-check lock-check secret-scan image-scan container-smoke verify check-docker-environment check-docker-project-clean check-working-tree-diff check-branch-diff

setup:
	@$(PYTHON) --version
	@sh scripts/ensure_docker.sh
	@docker compose version
	@node --version
	@pnpm --version
	@test -f $(ENV_FILE) || (echo "Нет файла конфигурации $(ENV_FILE)" >&2; exit 2)
	@$(PYTHON) -m pip install --user --break-system-packages "uv==$(UV_VERSION)"
	@$(UV) sync --frozen --extra dev
	@pnpm --dir frontend install --frozen-lockfile --package-import-method=copy

check-docker-environment:
	@test "$(DOCKER)" = "1" || (echo "Эта операция разрешена только с DOCKER=1" >&2; exit 2)
	@test -n "$(DOCKER_RUN_ID)" || (echo "Укажите непустой DOCKER_RUN_ID" >&2; exit 2)
	@test -f .env.example || (echo "Нет .env.example с настройками тестового контура" >&2; exit 2)
	@grep -qx 'APP_ENV=test' .env.example || (echo "APP_ENV в .env.example должен быть test" >&2; exit 2)
	@grep -Eq '^POSTGRES_DB=.*_test$$' .env.example || (echo "Имя тестовой БД в .env.example должно оканчиваться на _test" >&2; exit 2)

run:
ifeq ($(DOCKER),1)
	@$(MAKE) check-docker-environment DOCKER=1
	@$(COMPOSE) up --build --detach --wait
else
	@set -eu; \
	runtime_dir="$(RUNTIME_DIR)"; \
	mkdir -p "$$runtime_dir"; \
	for service in backend frontend; do \
		pid_file="$$runtime_dir/$$service.pid"; \
		if [ -f "$$pid_file" ]; then \
			pid=$$(cat "$$pid_file"); \
			if [ -n "$$pid" ] && kill -0 "$$pid" 2>/dev/null; then \
				echo "$$service уже запущен с PID $$pid; используйте make status или make down" >&2; \
				exit 2; \
			fi; \
			rm -f "$$pid_file"; \
		fi; \
	done; \
	nohup $(UV) run --frozen uvicorn app.main:app --host 0.0.0.0 --port "$${APP_PORT:-8000}" > "$$runtime_dir/backend.log" 2>&1 & echo $$! > "$$runtime_dir/backend.pid"; \
	nohup env VITE_API_PROXY_TARGET="http://127.0.0.1:$${APP_PORT:-8000}" pnpm --dir frontend exec vite --host 0.0.0.0 --port "$${FRONTEND_PORT:-5173}" > "$$runtime_dir/frontend.log" 2>&1 & echo $$! > "$$runtime_dir/frontend.pid"; \
	sleep 1; \
	for service in backend frontend; do \
		pid=$$(cat "$$runtime_dir/$$service.pid"); \
		if ! kill -0 "$$pid" 2>/dev/null; then \
			echo "$$service не запустился; смотрите $$runtime_dir/$$service.log" >&2; \
			cat "$$runtime_dir/$$service.log" >&2 || true; \
			$(MAKE) stop-local; \
			exit 2; \
		fi; \
	done; \
	echo "Backend и frontend запущены в фоне; используйте make status или make down"
endif

up:
ifeq ($(DOCKER),1)
	@$(MAKE) check-docker-environment DOCKER=1
endif
	@$(COMPOSE) up --build --detach --wait

down:
ifeq ($(DOCKER),1)
	@$(MAKE) check-docker-environment DOCKER=1
	@$(COMPOSE) down --volumes --remove-orphans
else
	@$(MAKE) stop-local
	@$(COMPOSE) down --remove-orphans
endif

stop-local:
	@set -eu; \
	runtime_dir="$(RUNTIME_DIR)"; \
	stopped=0; \
	for service in backend frontend; do \
		pid_file="$$runtime_dir/$$service.pid"; \
		if [ ! -f "$$pid_file" ]; then continue; fi; \
		pid=$$(cat "$$pid_file"); \
		if [ -n "$$pid" ] && kill -0 "$$pid" 2>/dev/null; then \
			kill "$$pid" 2>/dev/null || true; \
			echo "$$service остановлен (PID $$pid)"; \
			stopped=1; \
		fi; \
		rm -f "$$pid_file"; \
	done; \
	if [ "$$stopped" -eq 0 ]; then echo "Фоновые процессы make run не найдены"; fi

status:
	@set -eu; \
	project="$(DOCKER_PROJECT)"; \
	container_ids=""; \
	running_container_ids=""; \
	if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then \
		container_ids=$$(docker ps --all --filter "label=com.docker.compose.project=$$project" --quiet); \
		running_container_ids=$$(docker ps --filter "label=com.docker.compose.project=$$project" --quiet); \
	else \
		echo "Docker недоступен; контейнеры Compose-проекта $$project не проверены."; \
	fi; \
	if [ -n "$$container_ids" ]; then \
		echo "Состояние контейнеров Compose-проекта $$project:"; \
		docker ps --all --filter "label=com.docker.compose.project=$$project" --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'; \
		echo "Последние 50 строк логов каждого контейнера:"; \
		for container_id in $$container_ids; do \
			echo "==> $$container_id"; \
			docker logs --tail 50 "$$container_id" 2>&1 || true; \
		done; \
		if [ -n "$$running_container_ids" ]; then exit 0; fi; \
	fi; \
	echo "Контейнеры Compose-проекта $$project не запущены."; \
	echo "Проверка локально запущенного приложения:"; \
	backend_url="http://127.0.0.1:$${APP_PORT:-8000}"; \
	frontend_url="http://127.0.0.1:$${FRONTEND_PORT:-5173}"; \
	backend_ok=0; frontend_ok=0; \
	if curl --fail --silent --show-error "$$backend_url/health/live" >/dev/null && curl --fail --silent --show-error "$$backend_url/health/ready" >/dev/null; then \
		backend_ok=1; echo "Backend доступен: $$backend_url"; \
	else \
		echo "Backend недоступен: $$backend_url"; \
	fi; \
	if curl --fail --silent --show-error "$$frontend_url/" >/dev/null; then \
		frontend_ok=1; echo "Frontend доступен: $$frontend_url"; \
	else \
		echo "Frontend недоступен: $$frontend_url"; \
	fi; \
	if [ "$$backend_ok" -eq 1 ] && [ "$$frontend_ok" -eq 1 ]; then exit 0; fi; \
	exit 2

migrate:
ifeq ($(DOCKER),1)
	@$(MAKE) check-docker-environment DOCKER=1
	@$(COMPOSE) run --rm app alembic upgrade head
else
	@$(UV) run --frozen alembic upgrade head
endif

test:
	@echo '==> Тесты: запускаю изолированный Docker-контур'
	@$(MAKE) test-in-container DOCKER=1 DOCKER_RUN_ID="$(DOCKER_RUN_ID)"

test-in-container:
	@$(MAKE) check-docker-environment DOCKER=1
	@echo '==> Backend: применяю миграции к тестовой БД'
	@$(COMPOSE) run --rm --user root app alembic upgrade head
	@echo '==> Backend: запускаю pytest и проверку покрытия'
	@$(COMPOSE) run --rm --user root app pytest
	@echo '==> Frontend: подготавливаю test-образ и кэш pnpm'
	@$(MAKE) frontend-test-image
	@$(MAKE) ensure-pnpm-store
	@echo '==> Frontend: запускаю тесты из проектного образа'
	@docker run --rm -v "$(PNPM_STORE_VOLUME):/pnpm/store" "$(FRONTEND_TEST_IMAGE)"

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
ifeq ($(DOCKER),1)
	@$(MAKE) check-docker-environment DOCKER=1
	@$(COMPOSE) run --rm --user root app sh -c 'mkdir -p reports && ruff format --check --no-cache app tests scripts && ruff check --no-cache app tests scripts && MYPY_CACHE_DIR=/tmp/mypy mypy app tests scripts'
	@echo '==> SAST: начинаю проверку Python-кода Bandit'
	@set -eu; \
	if $(COMPOSE) run --rm --user root app bandit -q -r app scripts -lll -f json -o reports/bandit.json; then \
		echo '==> SAST: Bandit завершён успешно, отчёт: reports/bandit.json'; \
	else \
		status=$$?; echo '==> SAST: Bandit завершился с ошибкой, отчёт: reports/bandit.json' >&2; exit $$status; \
	fi
	@$(COMPOSE) run --rm --user root app sh -c 'pip freeze --exclude-editable > /tmp/requirements.txt && pip-audit --strict --format json -o reports/pip-audit.json -r /tmp/requirements.txt'
else
	@$(UV) run --frozen ruff format --check --no-cache app tests scripts
	@$(UV) run --frozen ruff check --no-cache app tests scripts
	@MYPY_CACHE_DIR=/tmp/mypy $(UV) run --frozen mypy app tests scripts
	@mkdir -p reports
	@echo '==> SAST: начинаю проверку Python-кода Bandit'
	@set -eu; \
	if $(UV) run --frozen bandit -q -r app scripts -lll -f json -o reports/bandit.json; then \
		echo '==> SAST: Bandit завершён успешно, отчёт: reports/bandit.json'; \
	else \
		status=$$?; echo '==> SAST: Bandit завершился с ошибкой, отчёт: reports/bandit.json' >&2; exit $$status; \
	fi
	@$(UV) run --frozen sh -c 'pip freeze --exclude-editable > /tmp/requirements.txt && pip-audit --strict --format json -o reports/pip-audit.json -r /tmp/requirements.txt'
endif
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
ifeq ($(DOCKER),1)
	@$(MAKE) check-docker-environment DOCKER=1
	@$(COMPOSE) run --rm app alembic upgrade head
	@$(COMPOSE) run --rm -e PYTEST_ADDOPTS=--no-cov app python scripts/check_critical_mutations.py
else
	@echo "Мутационная проверка разрешена только с DOCKER=1" >&2
	@exit 2
endif

migration-check:
ifeq ($(DOCKER),1)
	@$(MAKE) check-docker-environment DOCKER=1
	@$(COMPOSE) run --rm app python scripts/migration_check.py
else
	@echo "Проверка миграций разрешена только с DOCKER=1" >&2
	@exit 2
endif

backup:
ifeq ($(DOCKER),1)
	@$(MAKE) check-docker-environment DOCKER=1
endif
	@$(COMPOSE) run --rm pg-tools sh /scripts/backup_restore.sh backup /backups

restore:
ifeq ($(DOCKER),1)
	@$(MAKE) check-docker-environment DOCKER=1
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
ifeq ($(DOCKER),1)
	@$(MAKE) check-docker-environment DOCKER=1
	@$(COMPOSE) run --rm app alembic upgrade head
	@$(COMPOSE) run --rm pg-tools sh /scripts/backup_restore_check.sh /backups
else
	@echo "Проверка backup/restore разрешена только с DOCKER=1" >&2
	@exit 2
endif

lock-check:
	@echo '==> Lock-файлы: проверяю Python-зависимости'
	@$(UV) lock --check
	@echo '==> Lock-файлы: подготавливаю frontend-образ и pnpm-кэш'
	@$(MAKE) frontend-test-image
	@$(MAKE) ensure-pnpm-store
	@echo '==> Lock-файлы: проверяю frontend-зависимости'
	@docker run --rm -v "$(PNPM_STORE_VOLUME):/pnpm/store" "$(FRONTEND_TEST_IMAGE)" pnpm install --frozen-lockfile --prefer-offline --store-dir /pnpm/store

container-smoke:
ifeq ($(DOCKER),1)
	@$(MAKE) check-docker-environment DOCKER=1
	@set -eu; \
	cleanup() { $(COMPOSE) down --volumes --remove-orphans; }; \
	trap cleanup EXIT HUP INT TERM; \
	$(COMPOSE) up --build --detach --wait; \
	image_id="inventory-accountment-local-ubuntu-verify-app:latest"; \
	$(MAKE) image-scan IMAGE_ID="$$image_id"; \
	$(COMPOSE) run --rm app alembic upgrade head; \
	$(COMPOSE) exec -T app python scripts/container_smoke.py; \
	$(COMPOSE) ps; \
	cleanup; \
	trap - EXIT HUP INT TERM
else
	@echo "Контейнерный smoke-сценарий разрешён только с DOCKER=1" >&2
	@exit 2
endif

check-docker-project-clean:
	@$(MAKE) check-docker-environment DOCKER=1 DOCKER_RUN_ID="$(DOCKER_RUN_ID)"
	@test -z "$$($(COMPOSE) ps --all --quiet)" || (echo "Остались контейнеры тестового Compose-проекта" >&2; exit 2)
	@test -z "$$(docker volume ls --filter label=com.docker.compose.project=$(DOCKER_PROJECT) --quiet)" || (echo "Остались тома тестового Compose-проекта" >&2; exit 2)

check-working-tree-diff:
	@git diff --check

check-branch-diff:
	@base=$$(git merge-base HEAD "$(BASE_REF)") || (echo "Не удалось определить merge-base с $(BASE_REF)" >&2; exit 2); \
	git diff --check "$$base...HEAD"

verify:
	@set -eu; \
	cleanup() { echo '==> Очистка изолированного тестового Compose-проекта; pnpm-кэш $(PNPM_STORE_VOLUME) сохраняется'; $(MAKE) down DOCKER=1 DOCKER_RUN_ID="$(DOCKER_RUN_ID)"; }; \
	trap cleanup EXIT HUP INT TERM; \
	echo '==> Подготовка изолированного Docker-контура'; $(MAKE) check-docker-environment DOCKER=1 DOCKER_RUN_ID="$(DOCKER_RUN_ID)"; \
	echo '==> Проверка lock-файлов'; $(MAKE) lock-check DOCKER=1 DOCKER_RUN_ID="$(DOCKER_RUN_ID)"; \
	echo '==> Проверка качества, включая SAST Bandit'; $(MAKE) quality DOCKER=1 DOCKER_RUN_ID="$(DOCKER_RUN_ID)"; \
	echo '==> Автоматические тесты'; $(MAKE) test DOCKER=1 DOCKER_RUN_ID="$(DOCKER_RUN_ID)"; \
	echo '==> Мутационная проверка'; $(MAKE) mutation DOCKER=1 DOCKER_RUN_ID="$(DOCKER_RUN_ID)"; \
	echo '==> Проверка миграций'; $(MAKE) migration-check DOCKER=1 DOCKER_RUN_ID="$(DOCKER_RUN_ID)"; \
	echo '==> Проверка backup/restore'; $(MAKE) backup-restore-check DOCKER=1 DOCKER_RUN_ID="$(DOCKER_RUN_ID)"; \
	echo '==> Контейнерный smoke-сценарий'; $(MAKE) container-smoke DOCKER=1 DOCKER_RUN_ID="$(DOCKER_RUN_ID)"; \
	echo '==> Проверка очистки тестового проекта'; $(MAKE) check-docker-project-clean DOCKER=1 DOCKER_RUN_ID="$(DOCKER_RUN_ID)"; \
	echo '==> Проверка whitespace рабочей копии'; $(MAKE) check-working-tree-diff; \
	echo '==> Проверка whitespace веточной разницы'; $(MAKE) check-branch-diff; \
	cleanup; \
	trap - EXIT HUP INT TERM
	@echo '==> Проверки успешно завершены. Запускаю приложение: make up DOCKER=$(DOCKER)'
	@$(MAKE) up DOCKER="$(DOCKER)"
