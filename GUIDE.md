# Команды приложения и проверок

Весь стек работает в Docker Compose. GNU Make нужен только как интерфейс
команд на Linux; [Windows запускает те же сервисы напрямую](docs/DOCKER_WINDOWS.md).
Флаги DOCKER, LOCAL и TEST удалены и отклоняются с ошибкой.

## Внешний файл настроек

Путь задаётся снаружи через ENV_FILE; фактический путь и содержимое не сохраняйте
в репозитории. Файл имеет формат Docker Compose env, пример ключей — .env.example.
Используйте абсолютный путь: deploy меняет текущий каталог на корень проекта.

В Linux передайте путь интерактивно и экспортируйте переменную:

```bash
read -r -p 'Путь к файлу настроек: ' ENV_FILE
export ENV_FILE
make setup
make run
```

Все рабочие Make-команды (setup/run/up/down/status/migrate/backup/restore) и
обе команды deploy/deploy.sh читают ENV_FILE через общий scripts/compose.sh.
Путь с пробелами передаётся одним аргументом; файл не выполняется как shell-код.
При непустом ENV_FILE отсутствующий/недоступный файл вызывает отказ без fallback.
При незаданном или пустом ENV_FILE остаётся обычное поведение Compose: корневой
.env и значения по умолчанию. Переменные окружения имеют приоритет над файлом.
Не задавайте конкурирующий COMPOSE_ENV_FILES; используйте один способ настройки.

Прямой docker compose не читает ENV_FILE автоматически. В Linux:

```bash
docker compose --env-file "$ENV_FILE" up -d --build --wait
docker compose --env-file "$ENV_FILE" ps -a
```

В PowerShell:

```powershell
$env:ENV_FILE = Read-Host 'Путь к файлу настроек'
docker compose --env-file "$env:ENV_FILE" up -d --build --wait
docker compose --env-file "$env:ENV_FILE" ps -a
```

Передавайте тот же --env-file каждой прямой рабочей команде, включая down,
logs, build, run migrate и run pg-tools. Если внешний файл не используется,
опустите параметр целиком; не передавайте --env-file с пустым значением.
Для проверки используйте config --quiet: обычный config раскрывает значения.
Сам внешний файл не монтируется в контейнеры и не попадает в образ; Compose
передаёт только перечисленные в environment настройки сервисов. Внешняя БД
по-прежнему не поддерживается. Изменение POSTGRES_PASSWORD в файле не меняет
пароль существующей роли в уже созданном томе PostgreSQL.

Тестовые команды (test, quality, verify, lock-check, mutation, migration-check,
backup-restore-check, container-smoke, test-clean и их служебные цели) игнорируют
ENV_FILE. TEST_COMPOSE явно использует пустой compose.test.env, исключая
автозагрузку рабочего .env. Тестовые реквизиты остаются фиксированными;
TEST_API_PORT/TEST_FRONTEND_PORT задаются отдельно через окружение.
Прямые тестовые команды также должны передавать --env-file compose.test.env,
включая отдельный Linux test-runner. Docker build/run не читают ENV_FILE.

| Команда | Действие |
| --- | --- |
| make setup | Проверить Docker/Compose и собрать API/UI |
| make run / make up | Собрать и запустить PostgreSQL → Alembic → API → Frontend, дождаться готовности |
| make status | Статусы контейнеров и последние 50 строк логов |
| make down | Остановить приложение, сохранив том БД |
| make migrate | Применить Alembic в сервисе migrate к контейнерной БД |
| make backup | Дамп БД сервиса db в backups/ с метаданными и checksum |
| make restore BACKUP=backups/имя.dump | Восстановить дамп в отдельную БД того же контейнера |
| make test | Собрать тестовый Backend, применить миграции, pytest с покрытием и Frontend Vitest |
| make quality | Ruff, mypy, Bandit, Python audit, Frontend format/lint/typecheck/audit, gitleaks |
| make migration-check | Новая и заполненная временные БД, upgrade/downgrade и metadata |
| make mutation | Проверить обнаружение мутаций критических правил |
| make backup-restore-check | Реальное восстановление в отдельную тестовую БД и сверка данных |
| make container-smoke | HTTP smoke и сканирование фактически запущенного image ID |
| make verify | Полный обязательный контур и очистка тестового проекта |
| make test-clean | Удалить контейнеры и тома только тестового проекта |

Рабочий проект по умолчанию inventory-compose, том inventory_data.
PROJECT_NAME меняет его имя. Проверки используют отдельный проект
inventory-check-<TEST_RUN_ID>, compose.test.yaml и фиксированные обезличенные
реквизиты inventory_test. Тестовая конфигурация не берёт пароль и DATABASE_URL
из рабочего .env или ENV_FILE. PROJECT_NAME и TEST_PROJECT не должны совпадать.

Пример полного прогона из Unix shell:

~~~bash
make setup
make verify TEST_RUN_ID=local-check BASE_REF=origin/main
~~~

BASE_REF должен существовать в Git. Verify останавливается при первом отказе,
сохраняет ненулевой код и очищает тестовый проект через trap. Рабочее приложение
не запускается и не останавливается. Кэш pnpm сохраняется. Одновременные
проверки требуют разных ID и TEST_API_PORT/TEST_FRONTEND_PORT (по умолчанию
8001/5174). Запуск одного и того же проекта параллельно не поддерживается.

Рабочие APP_PORT/FRONTEND_PORT по умолчанию 8010/5180; PostgreSQL не публикует
порт на хост. Настройки необязательны: ENV_FILE или локальный .env
используют ключи .env.example.
Внешняя DATABASE_URL в Compose не принимается. Пароль нельзя менять только в
.env после создания тома: POSTGRES_* инициализируют новую БД, существующие
роли PostgreSQL автоматически не изменяются.

Restore по умолчанию не перезаписывает источник. Замена существующей отдельной
цели требует RESTORE_EXISTING=1, TARGET_DATABASE, TARGET_DATABASE_URL и
совпадающего CONFIRM_TARGET_DATABASE. Проверяйте точную цель до выполнения.
Все pg-tools операции идут в сервис db данного Compose-проекта.

Отчёты: reports/junit.xml, coverage.xml, htmlcov/, bandit.json, pip-audit.json,
pnpm-audit.json, gitleaks.json, trivy-image.json по мере прохождения этапов.
Linux test-runner сохраняет свои отчёты в reports/unix-tests/.
Файл отчёта не подтверждает успех сам по себе; следующий прогон может заменить его.

Порог Backend — 80%; отключать проверки для успеха запрещено. CI и независимое
одобрение актуального коммита остаются обязательными. Фактические результаты:
[TEST_DEFECTS.md](TEST_DEFECTS.md).
