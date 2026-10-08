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

Для запуска приложения с внешней PostgreSQL, когда `DATABASE_URL` в `.env`
указывает на неё, используйте:

```bash
make setup
make migrate
make run
```

Сам API в этом сценарии запускается напрямую, но `make setup` всё равно
готовит Docker, потому что `make test` всегда выполняется изолированно.

`LOCAL=1` использует только `.env.test`, базу с суффиксом `_test` и отдельный
Compose-проект. Для двух запусков в одной рабочей копии укажите свой
`LOCAL_RUN_ID` во всех командах одного запуска.

Старое имя публичного параметра запрещено намеренно. Передача этого имени
завершится ошибкой с подсказкой использовать `LOCAL=1`; внутренние `APP_ENV=test`,
`TEST_DATABASE_URL` и `.env.test` сохраняют свои имена.

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
