# Команды разработки и проверок

Сверено с Makefile и scripts/test-runner.mk ревизии 9701e9d. Команды Make выполняются в Unix shell; наличие Docker Desktop не устанавливает GNU Make в Windows.

## Два тестовых контура

| Контур | Запуск | Назначение |
| --- | --- | --- |
| Отдельный Linux test-образ | python scripts/build_test_image.py; Compose из [инструкции](docs/UNIX_TESTS.md) | Backend, Frontend, сборка UI и миграции; без Make/Node на хосте |
| Основной Make/CI | make verify DOCKER=1 | Полный обязательный контур, включая качество и безопасность |

Linux test-образ не управляет Docker с помощью socket и не выполняет полный verify. Не считать результаты этих контуров взаимозаменяемыми.

## Подготовка Make-окружения

Нужны Git, GNU Make, Python 3.11+, Node.js 24, pnpm 11.19.0 и Docker Compose. Make setup вызывает scripts/ensure_docker.sh: на поддерживаемой Ubuntu скрипт может устанавливать Docker и менять членство в группе docker. Это изменяет систему; после добавления в группу нужен новый сеанс.

~~~bash
make setup DOCKER=1
make up DOCKER=1 DOCKER_RUN_ID=local-check
make migrate DOCKER=1 DOCKER_RUN_ID=local-check

~~~

Setup проверяет версии/доступность инструментов, наличие файла конфигурации, устанавливает uv 0.5.29, затем выполняет uv sync --frozen --extra dev и pnpm install --frozen-lockfile. Он не создаёт рабочий файл настроек. Использовать .env.example только для тестового режима; обычный режим ожидает /etc/InventoryAccountment/InventoryAccountment.env.

## Основные команды

| Команда | Фактическое поведение |
| --- | --- |
| make run | Фоновые Uvicorn и Vite на 0.0.0.0; PID/логи в reports/runtime; отдельная БД должна быть доступна |
| make run DOCKER=1 / make up DOCKER=1 | Собирает и запускает тестовый Compose, ожидает healthcheck |
| make up | Запускает docker-compose.yaml с системным env-файлом |
| make migrate | Alembic upgrade head через uv, использует DATABASE_URL |
| make migrate DOCKER=1 | Alembic в тестовом контейнере app |
| make test | Всегда дочерний test-in-container DOCKER=1: миграции и pytest, затем сборка frontend-test и Vitest; сводки тестов и прогресс установки pnpm поясняются по-русски |
| make quality DOCKER=1 | Ruff format/check, mypy, Bandit, Python audit; Frontend quality/audit и gitleaks |
| make mutation DOCKER=1 | Контролируемые мутации; timeout/ошибка подготовки не считаются успехом |
| make migration-check DOCKER=1 | Чистая и заполненная временные БД, upgrade/downgrade, сравнение metadata |
| make backup / make restore | pg-tools выбранного Compose-проекта, а не произвольная внешняя DATABASE_URL |
| make backup-restore-check DOCKER=1 | Повреждение и восстановление только временных тестовых БД |
| make status DOCKER=1 | Состояние/последние 50 строк логов выбранного Compose-проекта |
| make down DOCKER=1 | Удаляет контейнеры, сеть и тома выбранного тестового проекта |
| make down | Останавливает локальные фоновые процессы и обычный Compose; его тома сохраняет |

Make test пересобирает Backend-образ перед миграциями и тестами, чтобы запуск использовал актуальные исходники и скрипты локализации. Отдельный Linux test-образ пересобирайте командой из [инструкции](docs/UNIX_TESTS.md) после изменения исходников или тестов.

В выводе установки pnpm счётчики поясняют число обработанных, взятых из кэша,
скачанных и добавленных пакетов; сетевые предупреждения сохраняют адрес и код,
указывая задержку и число оставшихся повторов. Сообщения Make о входе в каталог
подавлены: вместо них используются заголовки этапов Backend и Frontend.

Этап SAST начинается отдельным сообщением и после Bandit печатает блок с типом
анализа, числом найденных уязвимостей уровня High либо отметкой «всё чисто» и
путём к JSON-отчёту. При находках команда сохраняет ненулевой статус Bandit.

Make status возвращает успех уже при наличии работающего контейнера; это не полная readiness-проверка. Если контейнеров нет, проверяет HTTP Backend и Frontend на локальных портах APP_PORT/FRONTEND_PORT, по умолчанию 8000/5173.

LOCAL и TEST как Make-параметры отклоняются. Для разных запусков задавайте уникальный DOCKER_RUN_ID и используйте его во всех командах. Порты тестового Make-контура — 8001/5174; при параллельной публикации портов одного ID недостаточно, нужны также разные порты. Отдельный test-runner порты не публикует.

## Полный verify

~~~bash
make verify DOCKER=1 DOCKER_RUN_ID=local-check BASE_REF=origin/main

~~~

BASE_REF должен разрешаться в Git; выберите существующую базовую ветку проекта. Проверки выполняются последовательно:

1. lock-check: uv.lock и pnpm-lock.yaml.
2. quality: формат, Ruff, mypy, Bandit, аудит зависимостей и gitleaks.
3. test: Backend с покрытием 80% и Frontend Vitest (его порог coverage не задан).
4. mutation, migration-check и backup-restore-check.
5. container-smoke, проверка очистки проекта, whitespace рабочей и веточной разницы.

Внутри container-smoke после up вызывается Trivy, затем миграции и HTTP smoke. Сейчас имя образа для Trivy жёстко задано: inventory-accountment-local-ubuntu-verify-app:latest. Совпадение с образом конкретного прогона не гарантировано; это незавершённое требование приёмки, а не разрешённое исключение.

При первой ошибке verify прекращается, trap очищает тестовый Compose-проект. Внешний том pnpm inventory-accountment-pnpm-store сохраняется. После успешных проверок verify вызывает make up с переданным DOCKER: с DOCKER=1 тестовый контур снова запускается. Уберите его после проверки вручную:

~~~bash
make down DOCKER=1 DOCKER_RUN_ID=local-check

~~~

Не запускать verify без DOCKER=1, если последующий запуск обычного окружения не планируется.

## Отчёты и диагностика

Основной контур пишет reports/junit.xml, coverage.xml, htmlcov/, bandit.json, pip-audit.json, pnpm-audit.json, gitleaks.json, trivy-image.json по мере выполнения этапов. Наличие файла само по себе не доказывает успех или принадлежность актуальному коммиту. Последующий прогон может перезаписать его. Frontend JUnit в основном Make-контуре отдельно не настроен; в Linux test-runner он сохраняется.

При сбое сохранить команду, exit code, SHA и логи; отдельно запускать независимые проверки для диагностики допустимо, но это не отменяет отказ verify. Не снижать пороги, не отключать задания. Не считать старый образ проверкой текущей рабочей копии.

## Backup и restore

~~~bash
make backup DOCKER=1 DOCKER_RUN_ID=local-check
make restore DOCKER=1 DOCKER_RUN_ID=local-check BACKUP=backups/имя.dump

~~~

Замените имя дампа существующим. Restore по умолчанию создаёт отдельную БД; перезапись требует RESTORE_EXISTING=1, TARGET_DATABASE_URL, TARGET_DATABASE и совпадающего CONFIRM_TARGET_DATABASE. До разрушительной операции проверить точную цель и разрешение. Не применять удаление тестовых томов к рабочему проекту.

В обычном Compose pg-tools подключается к сервису db. Если приложение использует внешнюю DATABASE_URL, make backup не становится автоматически backup этой внешней БД. Для неё нужен отдельно согласованный план PostgreSQL backup/restore.

## Приёмка

Успешный verify не заменяет успешный CI актуального SHA, независимое одобрение, проверку критических файлов и живую демонстрацию. Последние сохранённые результаты и незавершённые проверки — в [TEST_DEFECTS.md](TEST_DEFECTS.md). В этой актуализации документации приложение и инфраструктура не запускались.
