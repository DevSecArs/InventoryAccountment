# Первоначальный запуск

Статус документа: инструкция для текущего каркаса приложения. Она позволяет
запустить PostgreSQL и HTTP-сервер, проверить жизнеспособность приложения и
готовность базы данных. После применения начальной миграции доступны
справочники единиц измерения, материалов и поставщиков.

## Что потребуется

- Docker Desktop с поддержкой Docker Compose;
- Python 3.11 или новее и локальное виртуальное окружение `venv`;
- PowerShell, открытый в корне репозитория.

Проверить Docker можно командой:

```powershell
docker compose version
```

## 1. Установить зависимости

Если окружение уже создано, установите проект из корня репозитория:

```powershell
venv\Scripts\python.exe -m pip install .
```

Если `venv` отсутствует, сначала установите Python 3.11+ и создайте её:

```powershell
py -3.11 -m venv venv
venv\Scripts\python.exe -m pip install .
```

## 2. Создать локальную конфигурацию

Создайте `.env` из примера. Он игнорируется Git, поэтому локальные параметры
и пароли не попадут в репозиторий.

```powershell
Copy-Item .env.example .env
```

Не коммитьте `.env` и не используйте учебный пароль `postgres` вне локальной
разработки.

## 3. Запустить PostgreSQL

В отдельном окне PowerShell выполните:

```powershell
docker compose -f docker-compose.yaml up -d db
docker compose -f docker-compose.yaml ps
```

Сервис `db` публикует PostgreSQL на `127.0.0.1:5433`. Данные хранятся в томе
`postgres_data`; обычная остановка контейнера том не удаляет.

## 4. Запустить HTTP-сервер

Перед первым запуском API примените миграцию схемы:

```powershell
venv\Scripts\python.exe -m alembic upgrade head
```

Проверить текущую ревизию можно командой:

```powershell
venv\Scripts\python.exe -m alembic current
```

Затем в корне репозитория выполните:

```powershell
venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

После запуска доступны:

- интерактивная документация: `http://127.0.0.1:8000/docs`;
- проверка жизнеспособности: `http://127.0.0.1:8000/health/live`;
- проверка доступности PostgreSQL: `http://127.0.0.1:8000/health/ready`.

Проверить ответы можно из второго окна PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/live
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

Ожидаемый ответ успешной проверки — `status: ok`.

## Текущие известные ограничения

1. Начальная миграция создаёт только модели уже реализованных справочников:
   единицы измерения, материалы и поставщики. Поступления, очередь, отчёты и
   связанные с ними таблицы пока не реализованы.
2. `Makefile` отсутствует, поэтому предусмотренные проектом команды
   `make setup`, `make run`, `make migrate` и `make verify` сейчас недоступны.

## Диагностика ошибки отсутствующей таблицы

Если при запросе, например, `GET /api/v1/units/`, сервер выводит ошибку
`psycopg2.errors.UndefinedTable: relation "units" does not exist`, это означает,
что соединение с PostgreSQL установлено, но начальная миграция не применена.

Не создавайте таблицы вручную через клиент PostgreSQL. Примените начальную
миграцию командой:

```powershell
venv\Scripts\python.exe -m alembic upgrade head
```

Затем перезапустите HTTP-сервер и повторите запрос к API.

Alembic использует тот же параметр `DATABASE_URL` из `.env`, что и приложение.
Если команда миграции сообщает `ModuleNotFoundError: No module named 'psycopg'`,
проверьте, что запускаете её после установки зависимостей из корня репозитория:

```powershell
venv\Scripts\python.exe -m pip install .
venv\Scripts\python.exe -m alembic upgrade head
```

## Остановка

Остановите сервер сочетанием `Ctrl+C`, затем остановите контейнер базы:

```powershell
docker compose -f docker-compose.yaml down
```

Команда не удаляет том `postgres_data`. Не используйте `down --volumes`, если
не намерены удалить локальные данные PostgreSQL.
