# Матрица автоматических проверок

Инвентаризация по исходникам 9701e9d. Наличие теста не означает, что он
выполнен на текущем коммите. Записанные результаты — в
[TEST_DEFECTS.md](../TEST_DEFECTS.md), полная целевая матрица — в [TASK.md](../TASK.md).

| Область | Реализованные проверки | Файлы |
| --- | --- | --- |
| Валидация | Номер документа, позиции, количество и точность, нормализация | tests/unit/test_validation.py |
| Пароли | Проверка пароля | tests/unit/test_password_verification.py |
| Период и CSV | Границы периода, escaping, опасные начальные символы, пустой CSV | tests/unit/test_supply_report.py |
| Test-образ | Исключение локальных зависимостей и .env, сохранение исходников отчётов | tests/unit/test_build_context.py |
| API, auth, справочники | Health/readiness, ошибки, CSRF, сессии, purge, CRUD, архивы, поиск и пагинация | tests/integration/test_api_catalogs.py |
| Черновики | Создание/чтение/PATCH, ограничения, ссылки, rollback и запрет изменения нечерновика | tests/integration/test_receipts.py |
| Проведение и история | Повтор без изменения updated_at и второй истории, legacy-статус, удаление черновика, два конкурентных проведения | tests/integration/test_receipt_posting.py |
| Отчёты | Период [from,to), исключение draft, фильтр материала, точные количества, JSON/CSV, ошибки периода | tests/integration/test_supply_reports.py |
| Frontend | 4 проверки API-клиента, 1 CatalogLayout, 2 ReportsPage: отсутствие периода и серверные строки/итоги | frontend/src/**/*.test.ts, frontend/src/**/*.test.tsx |
| Миграции | Чистая БД, обновление заполненной предыдущей схемы, ограничения, история с UNIQUE/индексом/FK, downgrade/upgrade, metadata | scripts/migration_check.py |
| Backup/restore | Восстановление изолированных данных, связей и ревизии | scripts/backup_restore_check.sh |
| Smoke | Health, регистрация, создание/чтение единицы через API | scripts/container_smoke.py |
| Mutation | Отказ целевых тестов при ослаблении критических проверок | scripts/check_critical_mutations.py |

## Запуск

- make test DOCKER=1 — Backend и Frontend через основной тестовый Compose.
- make migration-check DOCKER=1 — миграции.
- make backup-restore-check DOCKER=1 — реальное восстановление в тестовом контуре.
- make mutation DOCKER=1 — мутационные проверки.
- make quality DOCKER=1 — статические и security-проверки.
- make container-smoke DOCKER=1 — контейнерный сценарий и Trivy.
- make verify DOCKER=1 — обязательный полный контур.
- [Отдельный Linux-образ](UNIX_TESTS.md) — Backend, Frontend, сборка и миграции.

Команды требуют подготовленного окружения и отдельных тестовых ресурсов.
container-smoke пока использует фиксированный тег для сканирования:
совпадение image ID остаётся незавершённым требованием.

## Неполнота покрытия

Существующие проверки не закрывают всю матрицу TASK.md. В частности:
отказ commit и rollback истории, гонки проведения с PATCH/архивированием,
согласованность нескольких SQL-запросов отчёта, сумма 0.1+0.2 одного
материала, разные единицы, выгрузка больше страницы, все роли и ошибки новых
экранов, обновление кешей после проведения. В миграционном upgrade-сценарии
данные справочников до обновления не заменяют проверку всех старых документов.

Frontend coverage и браузерные E2E не настроены. Успешная сборка не
подтверждает поведение интерфейса. Smoke не проводит поступление и не
проверяет отчёт. Очередь, outbox и worker исключены из согласованного MVP;
синхронное проведение и отчёты уже реализованы и тестируются.
