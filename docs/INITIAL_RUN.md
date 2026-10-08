# Первоначальный запуск

Статус документа: инструкция для текущего каркаса приложения. Она позволяет
запустить PostgreSQL и HTTP-сервер, проверить жизнеспособность приложения и
готовность базы данных. После применения начальной миграции доступны
справочники единиц измерения, материалов и поставщиков.

## Что потребуется

- Python 3.11 и `uv 0.5.29` (команда `make setup` установит его при отсутствии);
- Node.js 24 с npm и pnpm `11.19.0`;
- PowerShell, открытый в корне репозитория.

Для `make setup` и проверок нужен Docker Desktop с поддержкой Docker Compose.
На Ubuntu `make setup` устанавливает отсутствующий Docker Engine с Compose и
просит повторно войти в SSH-сеанс после добавления пользователя в группу
`docker`. Обычные `make migrate` и `make run` работают с внешней PostgreSQL из
`DATABASE_URL` без запуска контейнера приложения.

Проверить Docker можно командой:

```powershell
docker compose version
```

## 1. Подготовить изолированное окружение

Для безопасной проверки изменений используйте тестовый режим. Он использует
безопасный `.env.example`, устанавливает Python-зависимости строго из `uv.lock`
и frontend-зависимости из
`pnpm-lock.yaml`:

```bash
make setup DOCKER=1
```

По умолчанию Compose-проект получает суффикс, зависящий от пути рабочей
копии. При параллельной работе из одной копии укажите разный `DOCKER_RUN_ID` во
всех командах конкретного запуска, например `DOCKER_RUN_ID=review-a`.

## 2. Запустить тестовый Docker-контур

```bash
make up DOCKER=1
make migrate DOCKER=1
```

Тестовая PostgreSQL не публикуется наружу. API доступен на
`http://127.0.0.1:8001`; проверьте его командами:

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health/live
Invoke-RestMethod http://127.0.0.1:8001/health/ready
```

После проверки удалите только временные ресурсы тестового контура:

```bash
make down DOCKER=1
```

## 3. Создать рабочую конфигурацию

Для обычного запуска рабочий файл всегда находится по пути
`/etc/InventoryAccountment/InventoryAccountment.env`. Создайте каталог и файл
на Linux-сервере, ограничьте к нему доступ и укажите строку подключения к
внешней PostgreSQL:

```bash
sudo install -d -m 750 /etc/InventoryAccountment
sudoedit /etc/InventoryAccountment/InventoryAccountment.env
sudo chmod 640 /etc/InventoryAccountment/InventoryAccountment.env
```

```ini
DATABASE_URL=postgresql+psycopg2://<USER>:<PASSWORD>@<DB_HOST>:5432/inventory
APP_ENV=production
APP_DEBUG=false
APP_HOST=0.0.0.0
APP_PORT=8000
```

`.env.example` предназначен только для изолированного тестового контура; не
копируйте его в рабочую конфигурацию и не коммитьте рабочий файл.

## 4. Проверить доступность внешней PostgreSQL

До запуска убедитесь, что адрес в `DATABASE_URL` доступен с сервера приложения
и что у учётной записи есть права на миграции. Обычные команды не поднимают
локальную БД: они используют подключение из системного файла конфигурации.

## 5. Запустить backend и frontend

Перед первым запуском API примените миграцию схемы:

```powershell
make migrate
```

Проверить текущую ревизию можно командой:

```powershell
python3 -m uv run --frozen alembic current
```

Затем в корне репозитория выполните:

```powershell
make run
```

После запуска доступны с сервера и других компьютеров доверенной сети:

- веб-интерфейс: `http://<IP_СЕРВЕРА>:5173`;
- интерактивная документация: `http://<IP_СЕРВЕРА>:8000/docs`;
- проверка жизнеспособности: `http://<IP_СЕРВЕРА>:8000/health/live`;
- проверка доступности PostgreSQL: `http://<IP_СЕРВЕРА>:8000/health/ready`.

Проверить ответы можно из второго окна PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health/live
Invoke-RestMethod http://127.0.0.1:8000/health/ready
```

Ожидаемый ответ успешной проверки — `status: ok`.

`make run` запускает frontend и backend в фоне. PID-файлы и логи находятся в
`reports/runtime/`; проверить процессы можно командой `make status`, остановить —
командой `make down`. Vite принимает запросы на `0.0.0.0:5173` и проксирует
`/api` и `/health` в FastAPI. Для доступа с другого компьютера откройте порты
`5173` и `8000` в firewall только для доверенной сети.

## Проверка перед изменением

Черновики поступлений и их позиции уже реализованы. Для обязательной локальной
проверки используйте `make verify DOCKER=1`: она включает качество, безопасность,
тесты, mutation, миграции, backup/restore и контейнерный сценарий. Полный
список команд, отчётов и способов диагностики приведён в [GUIDE.md](../GUIDE.md).

## Диагностика ошибки отсутствующей таблицы

Если при запросе, например, `GET /api/v1/units/`, сервер выводит ошибку
`psycopg2.errors.UndefinedTable: relation "units" does not exist`, это означает,
что соединение с PostgreSQL установлено, но начальная миграция не применена.

Не создавайте таблицы вручную через клиент PostgreSQL. Примените начальную
миграцию командой:

```powershell
make migrate
```

Затем перезапустите HTTP-сервер и повторите запрос к API.

Alembic использует тот же параметр `DATABASE_URL` из
`/etc/InventoryAccountment/InventoryAccountment.env`, что и приложение.
Если команда миграции сообщает `ModuleNotFoundError: No module named 'psycopg'`,
проверьте, что запускаете её после установки зависимостей из корня репозитория:

```powershell
make setup
make migrate
```

## Остановка

Остановите локальные backend и frontend командой `make down`. Если запущен
тестовый Docker-контур, используйте `make down DOCKER=1`.
