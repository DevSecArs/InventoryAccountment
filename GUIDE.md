# Руководство по локальной проверке

## Требования

Нужны Git, GNU Make, Python 3.11 (команда `python3`), Node.js 24, pnpm
11.19.0 и Docker с Compose. На Ubuntu `make setup` устанавливает отсутствующий
Docker Engine с Compose и попросит повторно войти в SSH-сеанс после добавления
пользователя в группу `docker`. В Windows запускайте Docker-команды из WSL2
либо совместимого Docker-исполнителя. Не сохраняйте в Git `.env`, дампы и
отчёты.

## Первый запуск

```bash
make setup DOCKER=1
make up DOCKER=1
make migrate DOCKER=1
```

Для запуска приложения с внешней PostgreSQL создайте
`/etc/InventoryAccountment/InventoryAccountment.env` с `DATABASE_URL`, затем
используйте:

```bash
make setup
make migrate
make run
```

Сам API в этом сценарии запускается напрямую, но `make setup` всё равно
готовит Docker, потому что `make test` всегда выполняется изолированно.

`make run` запускает backend на `0.0.0.0:8000` и frontend на `0.0.0.0:5173`.
`make up` и Docker-режим публикуют те же порты наружу; для доступа с другого
компьютера откройте их в firewall только для доверенной сети.

`DOCKER=1` использует только безопасный `.env.example`, базу с суффиксом `_test`
и отдельный Compose-проект. Для двух запусков в одной рабочей копии укажите свой
`DOCKER_RUN_ID` во всех командах одного запуска.

Передача `LOCAL=1` завершится ошибкой с подсказкой использовать `DOCKER=1`.
Внутренние `APP_ENV=test` и `TEST_DATABASE_URL` сохраняют свои имена.

## Команды

```bash
make run DOCKER=1              # запустить контур в фоне и дождаться healthcheck
make up DOCKER=1               # собрать и дождаться healthcheck
make down DOCKER=1             # удалить только тома текущего DOCKER-проекта
make migrate DOCKER=1          # применить миграции к тестовой БД
make test                     # всегда изолированные backend/frontend тесты и coverage
make quality DOCKER=1          # формат, lint, typing, SAST, dependency и secret scan
make mutation DOCKER=1         # критические контролируемые мутации
make backup DOCKER=1           # создать проверяемый дамп в backups/
make restore DOCKER=1 BACKUP=backups/<имя>.dump
make status DOCKER=1           # вывести статус и логи Docker-контура
make verify DOCKER=1           # полный блокирующий контур
```

`make restore` по умолчанию восстанавливает в отдельную БД. Перезапись
существующей цели требует `RESTORE_EXISTING=1`, URL, имя БД и совпадающее
`CONFIRM_TARGET_DATABASE`; не применяйте это к рабочим данным без отдельного
согласования.

## Что проверяет verify

Контур проверяет lock-файлы, форматирование, Ruff, mypy, Bandit, Python- и
frontend-аудит зависимостей, историю и рабочую копию gitleaks, backend и
frontend-тесты с coverage не ниже 80%, контролируемые мутации, миграции,
backup/restore, Trivy-скан того же образа, контейнерный API-сценарий, очистку
ресурсов и whitespace текущей и веточной разницы.

Отчёты находятся в `reports/`: `bandit.json`, `pip-audit.json`,
`pnpm-audit.json`, `gitleaks.json`, `trivy-image.json`, `junit.xml`,
`coverage.xml` и `htmlcov/`. Каталог игнорируется Git и сохраняется как
артефакт CI даже при ошибке.

## Диагностика и безопасная очистка

При сбое сначала прочтите название шага verify и его лог. `make down DOCKER=1`
удаляет исключительно Compose-ресурсы выбранного `DOCKER_RUN_ID`; обычный
`make down` не удаляет тома. Если проверка была прервана, выполните
`make down DOCKER=1 DOCKER_RUN_ID=<тот же id>`, затем повторите целевой шаг и
`make verify DOCKER=1`.

Перед приёмкой запустите в чистой копии `make setup DOCKER=1`, затем
`make verify DOCKER=1`. Локальный успех не заменяет публикацию ветки, CI,
независимое одобрение, настройку CODEOWNERS и живую демонстрацию.

## Пошаговые алгоритмы

### `make setup DOCKER=1`

1. Проверить версию Python.
2. Проверить наличие Docker.
3. Установить Docker Engine и Docker Compose при отсутствии.
4. Проверить версию Docker Compose.
5. Проверить версию Node.js.
6. Проверить версию pnpm.
7. Проверить наличие `.env.example`.
8. Установить `uv` указанной версии через `python3 -m pip`.
9. Установить Python-зависимости из `uv.lock`.
10. Установить frontend-зависимости из `frontend/pnpm-lock.yaml`.

### `make setup`

1. Проверить версию Python.
2. Проверить наличие Docker.
3. Установить Docker Engine и Docker Compose при отсутствии.
4. Проверить версию Docker Compose.
5. Проверить версию Node.js.
6. Проверить версию pnpm.
7. Проверить наличие `/etc/InventoryAccountment/InventoryAccountment.env`.
8. Установить `uv` указанной версии через `python3 -m pip`.
9. Установить Python-зависимости из `uv.lock`.
10. Установить frontend-зависимости из `frontend/pnpm-lock.yaml`.

### `make test`

1. Запустить `make test`.
2. Передать в дочернюю команду `DOCKER=1`.
3. Сформировать имя изолированного Compose-проекта с `DOCKER_RUN_ID`.
4. Проверить, что существует `.env.example`.
5. Проверить `APP_ENV=test` в `.env.example`.
6. Проверить суффикс `_test` у имени тестовой БД в `.env.example`.
7. Запустить тестовую PostgreSQL в изолированном Compose-контуре.
8. Применить Alembic-миграции к тестовой БД.
9. Запустить backend-тесты через `pytest` в Docker-контейнере приложения.
10. Запустить временный Docker-контейнер Node.js.
11. Скопировать в него исходники frontend без `node_modules`.
12. Установить pnpm.
13. Установить frontend-зависимости по `pnpm-lock.yaml`.
14. Запустить frontend-тесты командой `pnpm test:run`.

### `make run DOCKER=1`

1. Проверить `.env.example` и параметры тестового окружения.
2. Собрать образы тестового Compose-проекта.
3. Запустить PostgreSQL, backend и frontend в фоне.
4. Опубликовать backend на `0.0.0.0:8001` и frontend на `0.0.0.0:5174`.
5. Дождаться healthcheck сервисов и освободить терминал.

### `make run`

1. Создать `reports/runtime/` для PID-файлов и логов.
2. Проверить отсутствие уже работающих backend и frontend, запущенных через `make run`.
3. Запустить Uvicorn через `nohup` на `0.0.0.0` и записать PID и лог backend.
4. Загрузить настройки backend из `/etc/InventoryAccountment/InventoryAccountment.env`.
5. Запустить Vite через `nohup` на `0.0.0.0`, записать PID и лог frontend.
6. Направить запросы frontend к локальному backend через Vite proxy.
7. Проверить, что оба процесса не завершились сразу, и освободить терминал.

### `make up DOCKER=1`

1. Проверить `.env.example` и параметры тестового окружения.
2. Собрать образы тестового Compose-проекта.
3. Запустить PostgreSQL, backend и frontend в фоне.
4. Опубликовать backend на `0.0.0.0:8001` и frontend на `0.0.0.0:5174`.
5. Дождаться healthcheck сервисов.

### `make up`

1. Передать `/etc/InventoryAccountment/InventoryAccountment.env` в Docker Compose.
2. Собрать образы Compose-проекта.
3. Запустить PostgreSQL, backend и frontend в фоне.
4. Опубликовать backend и frontend на `0.0.0.0`.
5. Дождаться healthcheck сервисов.

### `make down DOCKER=1`

1. Проверить `.env.example` и параметры тестового окружения.
2. Остановить сервисы тестового Compose-проекта.
3. Удалить контейнеры, сети и тома тестового Compose-проекта.
4. Удалить изолированные ресурсы-сироты тестового Compose-проекта.

### `make down`

1. Передать `/etc/InventoryAccountment/InventoryAccountment.env` в Docker Compose.
2. Остановить фоновые backend и frontend, запущенные через `make run`.
3. Остановить сервисы Compose-проекта.
4. Удалить контейнеры, сети и ресурсы-сироты.
5. Сохранить тома Compose-проекта.

### `make migrate DOCKER=1`

1. Проверить `.env.example` и параметры тестового окружения.
2. Запустить временный контейнер приложения.
3. Применить Alembic-миграции к тестовой БД.
4. Удалить временный контейнер приложения.

### `make migrate`

1. Загрузить настройки из `/etc/InventoryAccountment/InventoryAccountment.env`.
2. Применить Alembic-миграции через `python3 -m uv`.

### `make test-in-container`

1. Проверить `.env.example` и параметры тестового окружения.
2. Применить Alembic-миграции к тестовой БД во временном контейнере приложения.
3. Запустить backend-тесты через `pytest` во временном контейнере приложения.
4. Запустить временный Docker-контейнер Node.js.
5. Скопировать в него исходники frontend без `node_modules`.
6. Установить pnpm и frontend-зависимости.
7. Запустить frontend-тесты командой `pnpm test:run`.

### `make quality DOCKER=1`

1. Проверить `.env.example` и параметры тестового окружения.
2. Создать каталог `reports`.
3. Проверить форматирование Python-кода через Ruff.
4. Запустить Ruff lint.
5. Запустить mypy.
6. Запустить Bandit и записать отчёт в `reports/bandit.json`.
7. Сформировать список Python-зависимостей.
8. Запустить pip-audit и записать отчёт в `reports/pip-audit.json`.
9. Запустить временный Docker-контейнер Node.js.
10. Установить frontend-зависимости.
11. Запустить frontend-проверки качества.
12. Запустить frontend audit и записать отчёт в `reports/pnpm-audit.json`.
13. Запустить `make secret-scan`.

### `make quality`

1. Проверить форматирование Python-кода через Ruff.
2. Запустить Ruff lint.
3. Запустить mypy.
4. Создать каталог `reports`.
5. Запустить Bandit и записать отчёт в `reports/bandit.json`.
6. Сформировать список Python-зависимостей.
7. Запустить pip-audit и записать отчёт в `reports/pip-audit.json`.
8. Запустить временный Docker-контейнер Node.js.
9. Установить frontend-зависимости.
10. Запустить frontend-проверки качества.
11. Запустить frontend audit и записать отчёт в `reports/pnpm-audit.json`.
12. Запустить `make secret-scan`.

### `make secret-scan`

1. Создать каталог `reports`.
2. Запустить Gitleaks в Docker-контейнере.
3. Проверить рабочую копию репозитория на секреты.
4. Записать обезличенный отчёт в `reports/gitleaks.json`.

### `make image-scan IMAGE_ID=<идентификатор>`

1. Проверить, что передан `IMAGE_ID`.
2. Создать каталог `reports`.
3. Проверить существование образа Docker.
4. Запустить Trivy в Docker-контейнере.
5. Проверить образ на уязвимости высокого и критического уровня.
6. Записать отчёт в `reports/trivy-image.json`.

### `make mutation DOCKER=1`

1. Проверить `.env.example` и параметры тестового окружения.
2. Применить Alembic-миграции к тестовой БД.
3. Запустить `scripts/check_critical_mutations.py` без расчёта покрытия.

### `make migration-check DOCKER=1`

1. Проверить `.env.example` и параметры тестового окружения.
2. Запустить `scripts/migration_check.py` во временном контейнере приложения.

### `make backup DOCKER=1`

1. Проверить `.env.example` и параметры тестового окружения.
2. Запустить временный контейнер `pg-tools`.
3. Создать дамп тестовой БД в `backups/`.

### `make backup`

1. Передать `/etc/InventoryAccountment/InventoryAccountment.env` в Docker Compose.
2. Запустить временный контейнер `pg-tools`.
3. Создать дамп БД в `backups/`.

### `make restore BACKUP=backups/<имя>.dump DOCKER=1`

1. Проверить `.env.example` и параметры тестового окружения.
2. Проверить наличие параметра `BACKUP`.
3. Проверить путь `BACKUP` в каталоге `backups/`.
4. Передать параметры целевой БД в контейнер `pg-tools`.
5. Запустить восстановление из указанного дампа.

### `make restore BACKUP=backups/<имя>.dump`

1. Передать `/etc/InventoryAccountment/InventoryAccountment.env` в Docker Compose.
2. Проверить наличие параметра `BACKUP`.
3. Проверить путь `BACKUP` в каталоге `backups/`.
4. Передать параметры целевой БД в контейнер `pg-tools`.
5. Запустить восстановление из указанного дампа.

### `make backup-restore-check DOCKER=1`

1. Проверить `.env.example` и параметры тестового окружения.
2. Применить Alembic-миграции к тестовой БД.
3. Запустить `scripts/backup_restore_check.sh`.
4. Создать дамп, повредить тестовые данные и восстановить их.
5. Проверить восстановленные данные.

### `make lock-check`

1. Проверить соответствие `uv.lock` зависимостям проекта.
2. Запустить временный Docker-контейнер Node.js.
3. Скопировать исходники frontend без `node_modules`.
4. Установить frontend-зависимости по `pnpm-lock.yaml`.

### `make status [DOCKER=1]`

1. Определить имя Compose-проекта: `inventory-accountment` либо тестовое имя с `DOCKER_RUN_ID`.
2. Проверить доступность Docker Engine.
3. Найти все контейнеры проекта, включая остановленные.
4. Вывести имена, статусы и опубликованные порты найденных контейнеров.
5. Вывести последние 50 строк логов каждого найденного контейнера.
6. Вернуть код `0`, если найден хотя бы один работающий контейнер.
7. При отсутствии работающих контейнеров вывести сообщение об этом.
8. Проверить локальный backend на `127.0.0.1:8000/health/live` и `/health/ready`.
9. Проверить локальный frontend на `127.0.0.1:5173`.
10. Вернуть код `0`, если локальные backend и frontend доступны; иначе вернуть код `2`.

### `make container-smoke DOCKER=1`

1. Проверить `.env.example` и параметры тестового окружения.
2. Зарегистрировать очистку ресурсов тестового Compose-проекта.
3. Собрать образы и запустить сервисы в фоне.
4. Дождаться healthcheck сервисов.
5. Запустить `make image-scan` для образа приложения.
6. Применить Alembic-миграции к тестовой БД.
7. Запустить `scripts/container_smoke.py` в контейнере приложения.
8. Вывести состояние сервисов Compose-проекта.
9. Удалить контейнеры, сети, тома и ресурсы-сироты тестового Compose-проекта.

### `make check-docker-environment DOCKER=1`

1. Проверить значение `DOCKER=1`.
2. Проверить непустое значение `DOCKER_RUN_ID`.
3. Проверить наличие `.env.example`.
4. Проверить значение `APP_ENV=test` в `.env.example`.
5. Проверить суффикс `_test` у `POSTGRES_DB` в `.env.example`.

### `make check-docker-project-clean DOCKER=1`

1. Выполнить `make check-docker-environment DOCKER=1`.
2. Проверить отсутствие контейнеров тестового Compose-проекта.
3. Проверить отсутствие томов тестового Compose-проекта.

### `make check-working-tree-diff`

1. Проверить рабочую копию командой `git diff --check`.

### `make check-branch-diff`

1. Определить общую базу текущей ветки и `BASE_REF`.
2. Проверить веточную разницу командой `git diff --check`.

### `make verify DOCKER=1`

1. Проверить `.env.example` и параметры тестового окружения.
2. Зарегистрировать очистку ресурсов тестового Compose-проекта.
3. Выполнить `make lock-check`.
4. Выполнить `make quality DOCKER=1`.
5. Выполнить `make test`.
6. Выполнить `make mutation DOCKER=1`.
7. Выполнить `make migration-check DOCKER=1`.
8. Выполнить `make backup-restore-check DOCKER=1`.
9. Выполнить `make container-smoke DOCKER=1`.
10. Выполнить `make check-docker-project-clean DOCKER=1`.
11. Выполнить `make check-working-tree-diff`.
12. Выполнить `make check-branch-diff`.
13. Удалить контейнеры, сети, тома и ресурсы-сироты тестового Compose-проекта.
