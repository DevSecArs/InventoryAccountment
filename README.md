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
- `frontend/` — веб-интерфейс; `tests/docker/` — проверки Compose и тестовые Docker-конфигурации.
- `reports/` — общие отчёты проверок.

## Запуск

Для Ubuntu Server нужны Docker Engine, Docker Compose v2 версии 2.20.0 или новее,
GNU Make и POSIX shell. Настройте Docker daemon и доступ текущего пользователя.
Создайте `.env` в корне проекта или запустите `make setup`: при отсутствии файла
команда создаст его из `.env.example` с правами 0600. Существующий `.env` не
перезаписывается. Setup проверяет Docker, daemon, исходные файлы и Compose;
может точечно добавить владельцу право чтения исходного файла или чтения/прохода
каталога, только если объект принадлежит текущему пользователю.

Из корня репозитория:

```bash
make setup
make build
make migrate
make up
make test
make quality
make verify
make status
```

`make test` собирает отдельные образы backend и frontend, запускает только
изолированную PostgreSQL, применяет миграции и выполняет backend-тесты через
`backend/tests/main.py`. Рабочий Compose и `.env` не используются; frontend
только собирается. Конфигурации находятся в `tests/docker/`. После завершения удаляются тестовые контейнеры, сеть и том.
Отчёты отдельного запуска сохраняются в `reports/<идентификатор-запуска>/`.
После SIGKILL или аварии хоста очистка не гарантируется.

`make quality` собирает тестовый backend-образ и выполняет Ruff, проверку
форматирования, mypy и Bandit. `make verify` последовательно запускает
`make test`, а после его успеха — `make quality`; при первой ошибке останавливается
и показывает итоговый статус обеих целей. `make status` показывает штатный вывод
`docker compose ps` из корня проекта без запуска setup; пустое окружение допустимо.

`make build` собирает backend/frontend и загружает образ PostgreSQL.
`make migrate` запускает только БД, ждёт её healthcheck и применяет миграции
до head в одноразовом контейнере из готового backend-образа. Команда не собирает
и не скачивает образы; при их отсутствии выполните `make build`. После изменения
файлов миграций пересоберите образы перед запуском `make migrate`.
`make up` запускает готовые образы в фоне, две реплики backend и ждёт healthcheck;
сборку и миграции он не выполняет. После успешного запуска откройте http://localhost.
При диагностике используйте `docker compose logs --tail=100 backend db frontend nginx`.

Зарегистрируйте первого администратора после открытия интерфейса.
Nginx — единственная внешняя HTTP-точка входа и публикует порт 80. Он направляет
`/api` и `/health` напрямую к двум backend, остальные запросы и WebSocket HMR —
к единственному Vite dev server. Vite proxy для API/health внутри сети направлен
через Nginx. Frontend, backend и PostgreSQL не публикуют порты на хост.

Dockerfile содержит цели backend и frontend. Backend запускает Uvicorn напрямую;
миграции применяются явно командой `make migrate`. Прямой `docker compose up`
не подготавливает схему. `/health/ready` проверяет соединение с PostgreSQL,
но не актуальность схемы. Зависимости устанавливаются
по backend/uv.lock и frontend/pnpm-lock.yaml. Backend и frontend запускаются
после готовности PostgreSQL и API соответственно.
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
curl http://localhost/health/ready
docker compose exec nginx nginx -t
docker compose ps
docker compose logs --tail=100 nginx backend
curl -sSI http://localhost/health/live
make migrate
docker compose down
```

Ответы backend содержат `X-Instance-ID` (hostname контейнера). Nginx обновляет
DNS backend каждые 5 секунд, пассивно исключает неисправный узел на 5 секунд и
повторяет только GET/HEAD один раз. Таймаут подключения 3 секунды ограничивает
установление соединения; read timeout 30 секунд ограничивает паузу между чтениями
от backend, но не полное время ответа. Отказоустойчивость покрывает отказ одной
backend-реплики на одном хосте; Nginx, Vite, PostgreSQL и хост остаются единичными
точками отказа.

Данные находятся в именованном томе inventory_data проекта inventory-compose.
`make down` и `docker compose down` сохраняют том. Существующий том того же
проекта переиспользуется. Для обновления выполните `make build`, `make migrate`,
затем `make up`. Для отката кода
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

Полный backend-набор в одноразовой изолированной среде:

```bash
make test
```

Точка входа `python backend/tests/main.py` обнаруживает тесты рекурсивно в
`backend/tests`, останавливается при первой ошибке и сохраняет JUnit/XML/HTML
отчёты и покрытие в корневой `reports/` (при запуске через Make — в уникальном
подкаталоге запуска).

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

Прежний DevOps-контур удалён по решению начать его заново. Запуск приложения
не зависит от старых scripts или Linux test-образа; `make test` использует
отдельные тестовые Docker-файлы. Автоматические CI/CD, сканирование образов,
backup/restore и сбор метрик предстоит спроектировать отдельно. Наличие Dockerfile
не подтверждает успешную сборку, релиз или приёмку.

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
