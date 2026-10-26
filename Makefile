SHELL := /bin/sh
.DEFAULT_GOAL := setup

PROJECT_ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
ROOT_Q := '$(subst ','"'"',$(PROJECT_ROOT))'

.PHONY: setup build up down migrate test quality

setup:
	@set -eu; \
	cd $(ROOT_Q); \
	if ! command -v docker >/dev/null 2>&1; then \
	  echo 'Ошибка: Docker CLI не найден в PATH. Установите Docker Engine и Compose v2.' >&2; exit 1; \
	fi; \
	if ! docker compose version >/dev/null 2>&1; then \
	  echo 'Ошибка: требуется плагин Docker Compose v2. Установите или обновите Docker Compose.' >&2; exit 1; \
	fi; \
	compose_version=$$(docker compose version --short 2>/dev/null | sed 's/^v//'); \
	if [ -z "$$compose_version" ] || [ "$$(printf '%s\n' 2.22.0 "$$compose_version" | sort -V | head -n 1)" != 2.22.0 ]; then \
	  echo 'Ошибка: требуется Docker Compose версии 2.22.0 или новее для --wait, --no-build и --pull never.' >&2; exit 1; \
	fi; \
	if ! docker info >/dev/null 2>&1; then \
	  echo 'Ошибка: Docker daemon недоступен. Запустите Docker Engine и настройте доступ текущего пользователя к daemon.' >&2; exit 1; \
	fi; \
	check_path() { \
	  path=$$1; kind=$$2; \
	  case "$$path" in "$(PROJECT_ROOT)"/*) ;; *) echo "Ошибка: путь вне проекта: $$path" >&2; return 1;; esac; \
	  if [ -L "$$path" ]; then echo "Ошибка: символические ссылки не поддерживаются: $$path" >&2; return 1; fi; \
	  if [ "$$kind" = dir ]; then \
	    [ -d "$$path" ] || { echo "Ошибка: каталог отсутствует: $$path" >&2; return 1; }; \
	    if [ ! -r "$$path" ] || [ ! -x "$$path" ]; then \
	      [ "$$(stat -c %u "$$path")" = "$$(id -u)" ] || { echo "Ошибка: нет доступа к каталогу и он не принадлежит текущему пользователю: $$path" >&2; return 1; }; \
	      mode=$$(stat -c %a "$$path"); [ $$(($$mode % 10 & 5)) -eq 5 ] || chmod u+rx "$$path" || { echo "Ошибка: невозможно исправить права каталога: $$path" >&2; return 1; }; \
	    fi; \
	  else \
	    [ -f "$$path" ] || { echo "Ошибка: файл отсутствует: $$path" >&2; return 1; }; \
	    if [ ! -r "$$path" ]; then \
	      [ "$$(stat -c %u "$$path")" = "$$(id -u)" ] || { echo "Ошибка: файл не читается и не принадлежит текущему пользователю: $$path" >&2; return 1; }; \
	      chmod u+r "$$path" || { echo "Ошибка: невозможно исправить права файла: $$path" >&2; return 1; }; \
	    fi; \
	  fi; \
	}; \
	for path in Dockerfile .dockerignore docker-compose.yml .env.example backend backend/pyproject.toml backend/uv.lock backend/app backend/alembic.ini backend/alembic frontend frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml frontend/index.html frontend/vite.config.ts frontend/eslint.config.js frontend/prettier.config.mjs frontend/.prettierignore frontend/tsconfig.json frontend/tsconfig.app.json frontend/tsconfig.node.json frontend/src; do \
	  case "$$path" in backend|backend/app|backend/alembic|frontend|frontend/src) check_path "$(PROJECT_ROOT)/$$path" dir;; *) check_path "$(PROJECT_ROOT)/$$path" file;; esac; \
	done; \
	find backend/app backend/alembic frontend/src -type d \( -name node_modules -o -name .pnpm-store -o -name .venv -o -name venv -o -name reports -o -name backups \) -prune -o -type f -print | while IFS= read -r path; do \
	  [ -L "$$path" ] && { echo "Ошибка: символическая ссылка в исходном дереве: $$path" >&2; exit 1; }; \
	  [ -r "$$path" ] || check_path "$$path" file; \
	done; \
	if [ ! -e .env ]; then (umask 077; set -C; cat .env.example > .env) 2>/dev/null || { echo 'Ошибка: не удалось безопасно создать .env.' >&2; exit 1; }; chmod 600 .env || { echo 'Ошибка: не удалось установить права 0600 для .env.' >&2; exit 1; }; fi; \
	check_path "$(PROJECT_ROOT)/.env" file; \
	docker compose config --quiet || { echo 'Ошибка: конфигурация Docker Compose некорректна.' >&2; exit 1; }; \
	echo 'Проверка окружения завершена.'

build: setup
	@set -eu; cd $(ROOT_Q); docker compose build; docker compose pull db

up: setup
	@set -eu; cd $(ROOT_Q); \
	if ! docker compose up -d --wait --no-build --pull never; then \
	  echo 'Ошибка: запуск или проверка готовности не выполнены. Для диагностики: docker compose logs --tail=100 backend db frontend. Если образы отсутствуют, выполните make build.' >&2; exit 1; \
	fi; \
	echo 'Приложение готово: http://localhost:5173'

down:
	@set -eu; cd $(ROOT_Q); \
	if ! command -v docker >/dev/null 2>&1; then \
	  echo 'Ошибка: Docker CLI не найден в PATH.' >&2; exit 1; \
	fi; \
	if ! docker compose version >/dev/null 2>&1; then \
	  echo 'Ошибка: требуется плагин Docker Compose v2.' >&2; exit 1; \
	fi; \
	if ! docker compose down; then \
	  echo 'Ошибка: не удалось остановить проект Docker Compose.' >&2; exit 1; \
	fi; \
	echo 'Контейнеры и сеть проекта остановлены; тома сохранены.'

migrate: setup
	@set -eu; cd $(ROOT_Q); \
	backend_image=$$(docker compose config --images backend | grep 'backend' 2>/dev/null) || { echo 'Ошибка: не удалось определить backend-образ из конфигурации Compose.' >&2; exit 1; }; \
	db_image=$$(docker compose config --images db 2>/dev/null) || { echo 'Ошибка: не удалось определить образ базы данных из конфигурации Compose.' >&2; exit 1; }; \
	if [ -z "$$backend_image" ] || ! docker image inspect "$$backend_image" >/dev/null 2>&1; then \
	  echo 'Ошибка: готовый backend-образ не найден. Выполните make build.' >&2; exit 1; \
	fi; \
	if [ -z "$$db_image" ] || ! docker image inspect "$$db_image" >/dev/null 2>&1; then \
	  echo 'Ошибка: готовый образ базы данных не найден. Выполните make build.' >&2; exit 1; \
	fi; \
	if ! docker compose up -d --wait --no-build --pull never --no-recreate db; then \
	  echo 'Ошибка: база данных не запустилась или не прошла healthcheck. Диагностика: docker compose logs --tail=100 db.' >&2; exit 1; \
	fi; \
	if ! docker compose run --rm --no-deps --pull never backend alembic upgrade head; then \
	  echo 'Ошибка: применение миграций завершилось неуспешно. База данных оставлена работающей.' >&2; exit 1; \
	fi; \
	echo 'Миграции успешно применены до head.'

test:
	# Проверки docker
	@set -eu; \
	cd $(ROOT_Q); \
	if ! command -v docker >/dev/null 2>&1; then echo 'Ошибка: Docker CLI не найден в PATH.' >&2; exit 1; fi; \
	if ! docker compose version >/dev/null 2>&1; then echo 'Ошибка: требуется Docker Compose v2.' >&2; exit 1; fi; \
	compose_version=$$(docker compose version --short 2>/dev/null | sed 's/^v//'); \
	if [ -z "$$compose_version" ] || [ "$$(printf '%s\n' 2.22.0 "$$compose_version" | sort -V | head -n 1)" != 2.22.0 ]; then \
	  echo 'Ошибка: требуется Docker Compose версии 2.22.0 или новее.' >&2; exit 1; \
	fi; \
	if ! docker info >/dev/null 2>&1; then echo 'Ошибка: Docker daemon недоступен.' >&2; exit 1; fi; \
	for path in tests/docker/Dockerfile.test tests/docker/Dockerfile.test.dockerignore tests/docker/docker-compose.test.yml backend/pyproject.toml backend/uv.lock backend/alembic.ini backend/alembic backend/app backend/tests frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml frontend/src; do \
	  [ -e "$$path" ] || { echo "Ошибка: отсутствует исходник тестовой сборки: $$path" >&2; exit 1; }; \
	done; \
	# Создание папки для отчётов
	mkdir -p reports; \
	run_id=$$(date -u +%Y%m%dt%H%M%Sz)-$$$$; \
	case "$$run_id" in *[!a-zA-Z0-9_-]*) echo 'Ошибка: недопустимый идентификатор тестового запуска.' >&2; exit 1;; esac; \
	project="inventory-test-$$run_id"; \
	case "$$project" in inventory-test-[a-zA-Z0-9_-]*) ;; *) echo 'Ошибка: не удалось определить безопасный проект Compose.' >&2; exit 1;; esac; \
	mkdir "reports/$$run_id" || { echo 'Ошибка: не удалось создать каталог отчётов.' >&2; exit 1; }; \
	compose() { docker compose --env-file /dev/null -f tests/docker/docker-compose.test.yml -p "$$project" "$$@"; }; \
	cleanup() { \
	  result=$$?; trap - EXIT HUP INT TERM; \
	  if ! compose down --volumes; then \
	    echo "Ошибка очистки тестового проекта $$project; проверьте его ресурсы вручную." >&2; \
	    if [ "$$result" -eq 0 ]; then result=1; fi; \
	  fi; \
	  exit "$$result"; \
	}; \
	trap cleanup EXIT; \
	trap 'exit 129' HUP; trap 'exit 130' INT; trap 'exit 143' TERM; \
	export TEST_HOST_REPORTS_DIR="$(PROJECT_ROOT)/reports/$$run_id"; \
	export TEST_HOST_UID=$$(id -u); export TEST_HOST_GID=$$(id -g); \
		# Прогон тестов
        compose build backend-test; \
        compose up -d --wait db; \
        compose run --rm --no-deps backend-test alembic upgrade head; \
        compose run --rm --no-deps backend-test python tests/main.py; \
		echo '=============== Начало мутационных тестов ==============='; \
        compose run --rm --no-deps backend-test sh -c 'mutmut run --max-children 1 && mutmut results | tee /workspace/reports/mutations.txt && ! grep -Eq ": (survived|no tests)$$" /workspace/reports/mutations.txt'

quality:
	@set -eu; \
	cd $(ROOT_Q); \
	docker build -q -f tests/docker/Dockerfile.test --target backend-test -t inventory-backend-test .; \
	docker run --rm inventory-backend-test sh -c ' \
		echo "=============== Запуск линтера ===============" && \
		ruff check app tests && ruff format --check app tests && mypy app && \
		echo "=============== Линтеры пройдены. Запуск SAST Bandit ===============" && \
		bandit -r app \
		'
