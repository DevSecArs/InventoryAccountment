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
make setup LOCAL=1
make up LOCAL=1
make migrate LOCAL=1
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

`LOCAL=1` использует только безопасный `.env.example`, базу с суффиксом `_test`
и отдельный Compose-проект. Для двух запусков в одной рабочей копии укажите свой
`LOCAL_RUN_ID` во всех командах одного запуска.

Старое имя публичного параметра запрещено намеренно. Передача этого имени
завершится ошибкой с подсказкой использовать `LOCAL=1`; внутренние `APP_ENV=test`,
`TEST_DATABASE_URL` сохраняет своё имя.

## Команды

```bash
make run LOCAL=1              # запустить контур в foreground
make up LOCAL=1               # собрать и дождаться healthcheck
make down LOCAL=1             # удалить только тома текущего LOCAL-проекта
make migrate LOCAL=1          # применить миграции к тестовой БД
make test                     # всегда изолированные backend/frontend тесты и coverage
make quality LOCAL=1          # формат, lint, typing, SAST, dependency и secret scan
make mutation LOCAL=1         # критические контролируемые мутации
make backup LOCAL=1           # создать проверяемый дамп в backups/
make restore LOCAL=1 BACKUP=backups/<имя>.dump
make container-check LOCAL=1  # собрать, scan образа и выполнить HTTP smoke
make verify LOCAL=1           # полный блокирующий контур
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

При сбое сначала прочтите название шага verify и его лог. `make down LOCAL=1`
удаляет исключительно Compose-ресурсы выбранного `LOCAL_RUN_ID`; обычный
`make down` не удаляет тома. Если проверка была прервана, выполните
`make down LOCAL=1 LOCAL_RUN_ID=<тот же id>`, затем повторите целевой шаг и
`make verify LOCAL=1`.

Перед приёмкой запустите в чистой копии `make setup LOCAL=1`, затем
`make verify LOCAL=1`. Локальный успех не заменяет публикацию ветки, CI,
независимое одобрение, настройку CODEOWNERS и живую демонстрацию.

## Пошаговые алгоритмы

### `make setup LOCAL=1`

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
2. Передать в дочернюю команду `LOCAL=1`.
3. Сформировать имя изолированного Compose-проекта с `LOCAL_RUN_ID`.
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
