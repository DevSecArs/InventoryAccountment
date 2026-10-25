# InventoryAccountment — складской учёт

FastAPI / SQLAlchemy / PostgreSQL и React / TypeScript / Vite.
Приложение содержит авторизацию, справочники единиц, материалов и поставщиков,
поступления, проведение, историю статусов и отчёт по поставкам с CSV.
UI создаёт поступление с одной позицией; API поддерживает несколько позиций.

## Структура

- `backend/app/` — Python-приложение.
- `backend/alembic/` и `backend/alembic.ini` — миграции.
- `backend/pyproject.toml` и `backend/uv.lock` — зависимости и настройки Python.
- `backend/tests/` — unit- и интеграционные тесты backend.
- `frontend/` — веб-интерфейс; `tests/docker/` — проверки Compose.
- `reports/` — общие отчёты проверок.

## Запуск

Нужны Docker Engine или Docker Desktop с Linux containers и Docker Compose v2.
Из корня репозитория:

```bash
docker compose up -d --build --wait
```

Откройте http://localhost:5173 и зарегистрируйте первого администратора.
Frontend работает через Vite dev server. Только он публикует порт 5173.
`/api` и `/health` проксируются на `backend:8000` внутри Docker.
Backend и PostgreSQL не публикуют порты на хост.

Dockerfile содержит цели backend и frontend. Зависимости устанавливаются
по backend/uv.lock и frontend/pnpm-lock.yaml. После готовности PostgreSQL backend
применяет Alembic-миграции, запускает API; frontend ждёт готовности API.
Backend работает от app, frontend — от node, PostgreSQL — от postgres.
Локальные node_modules не копируются в образ.

Compose автоматически читает необязательный `.env`; образец — [.env.example](.env.example).
Для другого файла: `docker compose --env-file /путь/к/файлу up -d --build --wait`.
Примерный пароль предназначен для локального учебного запуска.
Изменение переменных не меняет реквизиты уже созданной БД.

## Управление и диагностика

```bash
docker compose ps
docker compose logs --tail=100 backend db frontend
curl http://localhost:5173/health/ready
docker compose exec backend alembic current
docker compose down
```

Данные находятся в именованном томе inventory_data проекта inventory-compose.
`down` сохраняет том. Существующий том того же проекта переиспользуется.
Для обновления: повторите команду запуска со сборкой. Для отката кода
вернитесь к совместимой ревизии и пересоберите образы. Миграции и данные
автоматически не откатываются. Перед работой с ценной БД нужна резервная копия.
Логи идут в stdout/stderr, readiness проверяет PostgreSQL.

## Проверки без оболочек команд

Для локальных проверок backend нужны Python 3.12 и uv; frontend — Node.js 24
и pnpm 11.19.0. Установка зависимостей и запуск unit-тестов:

```bash
cd backend
uv sync --locked --extra dev
uv run --extra dev pytest tests/unit
uv run --extra dev ruff check app tests
uv run --extra dev mypy app
uv run --extra dev bandit -r app
uv run --extra dev pip-audit
```

Команды Python выполняются из `backend/`.
Порог покрытия бизнес-логики в backend/pyproject.toml — 80%.
Отчёты создаются в корневом `reports/`. Unit-тесты покрывают
только часть приложения; команда может завершиться ошибкой порога, даже если
все выбранные тесты прошли. Полное покрытие проверяется вместе с интеграционными
тестами; порог не снижен.

```bash
cd ../frontend
pnpm install --frozen-lockfile
pnpm quality
pnpm test:run
pnpm build
```

Проверка Docker-конфигурации отдельно от unit-тестов, из корня:

```bash
docker compose --env-file .env.example config --quiet
python -m unittest tests.docker.test_simple_docker -v
```

Интеграционные тесты требуют отдельную PostgreSQL, применённые миграции,
`APP_ENV=test` и одинаковые `DATABASE_URL` / `TEST_DATABASE_URL` с именем БД,
заканчивающимся на `_test`. В отдельном терминале с этими переменными, из корня репозитория:

```bash
cd backend
uv run alembic upgrade head
uv run --extra dev pytest tests/unit tests/integration
```

Не используйте рабочую БД: тесты очищают таблицы. Локальный `.env` автоматически
читает Compose, но не приложение; для uv-команд задавайте переменные явно.

## Состояние инфраструктуры

Прежний DevOps-контур удалён по решению начать его заново. Запуск и проверки
не требуют Makefile, старых scripts или Linux test-образа. Автоматические
CI/CD, сканирование образов, backup/restore и сбор метрик предстоит спроектировать
отдельно. Наличие Dockerfile не подтверждает успешную сборку, релиз или приёмку.

Правила изменений — [AGENTS.md](AGENTS.md).

Перенос backend — задача без номера: цель — изолировать Python-проект,
сохранив приложение, миграции и тесты. Критические изменения: Dockerfile,
.dockerignore, backend/pyproject.toml, backend/alembic.ini и пути тестов.
Новых миграций и изменений данных нет. Проверка: сборка backend, существующие
тесты и миграции на отдельной БД; перед слиянием нужно независимое одобрение.
Откат — возврат структуры и путей предыдущей ревизии, без изменения БД.

Локальная проверка переноса: backend-образ собран с `uv sync --locked`;
миграции применены на новой отдельной БД; 61 backend-тест прошёл,
покрытие 84,72%; четыре проверки Compose и `git diff --check` прошли.
Отчёты находятся в `reports/`. Рабочие контейнеры не перезапускались;
CI, релиз и человеческая приёмка не проводились.
