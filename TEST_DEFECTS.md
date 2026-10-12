# Результаты тестирования MVP

## Актуализация после исправления блокировок

По отдельному поручению пользователя исправлен DEF-001 и подготовлен отдельный
Linux test-образ. Исторический отчёт ниже сохранён; его прежние блокировки и
утверждения о выполнении новых тестов уточняются результатами этого раздела.

- Блокировки Receipt, ReceiptItem и Material ограничены целевой таблицей через
  `FOR UPDATE OF`: eager LEFT JOIN больше не пытается блокировать nullable-сторону.
  Проверки статуса и транзакции сохранены. Миграций данных нет.
- Образ `inventory-accountment-tests:local`, платформа `linux/amd64`, image ID
  `sha256:bfee5b49baf8357c599aeeeb90e3db86c8c3a7991a587e794e854f77aa309fff`.
- Образ включает Python, Node.js, pnpm, GNU Make и актуальные исходники/тесты.
  Контекст формируется без чтения локального node_modules; WSL-ссылки и реальные
  `.env` не передаются. Каталог исходников `features/reports` сохраняется.
- Vite читает переменные через `loadEnv`, без обращения к нетипизированному
  глобальному `process`; сборка интерфейса проверена в Linux.
- Новые регрессии: удаление черновика, конкурентное проведение с одной историей,
  неизменность updated_at при повторе, сохранность исходников отчётов в контексте.

Фактические команды:

```text
python scripts/build_test_image.py
docker compose -p inventory-tests-fix-20261012 -f compose.test-runner.yaml run --rm tests
docker compose -p inventory-tests-fix-20261012 -f compose.test-runner.yaml down --volumes
```

Итоговый запуск завершился с exit code 0:

| Проверка | Результат |
| --- | --- |
| Backend: актуальные unit и integration | 55 passed, 18 предупреждений об устаревающих API зависимостей |
| Покрытие Backend | 82,61%; порог 80% не изменялся |
| Frontend | 5 passed |
| TypeScript и production-сборка Frontend | Успешно |
| Alembic | Чистая БД, обновление, downgrade/upgrade последней ревизии и сравнение metadata — успешно |
| Ruff check/format изменённых Python-файлов | Успешно |
| git diff --check | Успешно |

Артефакты итогового прогона: `reports/unix-tests/run.log`,
`backend-junit.xml`, `frontend-junit.xml`, `coverage.xml`, `htmlcov/`.
Тестовый контейнер БД, том и сеть удалены; образ сохранён для повторного запуска.

Уточнение прежней отчётности: в старом образе отсутствовали
`test_supply_report.py` и `test_receipt_posting.py`. Прежние «23 passed» относятся
к старым unit-тестам, а общий `reports/junit.xml` был перезаписан последним
unit-прогоном. Итоговый новый прогон действительно содержит новые файлы.

Полный `make verify DOCKER=1` не выполнен: новый образ предназначен для тестов
без доступа к Docker socket, а исходный verify управляет Docker и включает
дополнительные проверки. SAST/audit, полный статический анализ, mutation,
backup/restore, сканирование образа и CI не подтверждены этим запуском.
Полнота матрицы TASK.md, в частности тестов новых экранов Frontend, не заявляется.
Это успешная проверка имеющегося набора, а не разрешение на слияние или выпуск.

Для PR отдельно перечислить критические файлы: `Dockerfile.tests`,
`compose.test-runner.yaml`, `scripts/build_test_image.py`, `scripts/test-runner.mk`,
новые/изменённые регрессионные тесты. Инструкция и откат:
[docs/UNIX_TESTS.md](docs/UNIX_TESTS.md). Исходные изменения Terra сохранены.

## Контекст

- Задача в трекере: отсутствует; источником требований служит `TASK.md`.
- Исходный commit: `faecb2a3a1cbc05b3958b8d087b36d549716c679`.
- Ветка: `codex/mvp-test-coverage`.
- Тестовый проект Docker: `inventory-accountment-local-terra-baseline-20261012`.
- Проверяемая миграция head: `a5b7c9d1e004`.
- Рабочие данные, production Compose и сторонние контейнеры не использовались.

## Выполненные команды и результаты

| Команда | Exit code | Результат |
| --- | ---: | --- |
| `make test DOCKER=1 DOCKER_RUN_ID=terra-baseline-20261012` | 1 | Заблокирована: GNU Make отсутствует в Windows PATH. |
| `docker compose ... run app alembic upgrade head` | 0 | Миграции применены к изолированной PostgreSQL. |
| `docker compose ... run app pytest tests/unit tests/integration -xvv` | 1 | Собрано 45: 32 passed, 1 failed до `-x`; XML/JUnit записан в `reports/junit.xml`. |
| `docker compose ... run app pytest tests/unit -q` | 1 | 23 passed; тесты не обращались к DB-фикстурам. Exit 1 только из-за корректно сохранённого глобального порога coverage: 35.78% < 80%. |
| `pnpm --dir frontend test:run` | 1 | Локальный `vitest` недоступен как Windows executable. |
| `docker build --target frontend-test ...` | 1 | Docker не смог прочитать `frontend/node_modules`; стандартное исключение из `.dockerignore` не применяется к недоступной Windows-ссылке. |

Покрытие полного набора не получено: тестовый прогон закончен первым продуктовым дефектом. Имеющиеся артефакты backend: `reports/junit.xml`, `reports/coverage.xml`, `reports/htmlcov/`. Frontend JUnit и coverage отсутствуют из-за блокировки сборки test-образа.

## Матрица проверок

| ID | Реализация | Результат |
| --- | --- | --- |
| U01–U03, U06 | `tests/unit/test_validation.py`, `test_password_verification.py` | passed в целевом прогоне до первого сбоя |
| U04–U05 | `tests/unit/test_supply_report.py` | passed в отдельном unit-прогоне |
| I01–I05 | существующие `tests/integration/test_api_catalogs.py` | passed в целевом прогоне |
| I06 | `tests/integration/test_receipts.py::test_receipt_draft_create_read_and_replace` | failed, DEF-001 |
| I09–I10, I13–I14 | `tests/integration/test_receipt_posting.py` | реализовано; blocked дефектом PATCH/блокировки в общем прогоне |
| I07–I08, I11–I17, C01–C06, R01–R04, M01–M06 | — | not run: не реализованы полностью в рамках текущего прогона |
| F01–F12 | — | blocked: frontend test-образ не собран |

## Подтверждённые дефекты

### DEF-001 — PATCH черновика завершает запрос ошибкой PostgreSQL

- Приоритет: высокий. Пользователь не может изменять созданный черновик; это нарушает I06 и согласованный сценарий `draft → posted`.
- Требование: `TASK.md`, I06; `docs/Техническое_задание.md`, создание и редактирование черновика.
- Минимальные данные: активные единица `KG`, поставщик `SUP`, материалы `M1` и `M2`, черновик `DOC-1` с одной строкой.
- Воспроизведение: выполнить `tests/integration/test_receipts.py::test_receipt_draft_create_read_and_replace` в изолированном Docker-контуре и отправить `PATCH /api/v1/receipts/{id}` с заменой строки.
- Ожидание: HTTP 200, черновик содержит новую строку.
- Факт: PostgreSQL возвращает `FOR UPDATE cannot be applied to the nullable side of an outer join`; HTTP-контракт не формируется.
- Падающий тест: `tests/integration/test_receipts.py::test_receipt_draft_create_read_and_replace`.
- Повторное воспроизведение: подтверждено подробным запуском `pytest ... -xvv`.
- Область: backend, `get_receipt_for_update`; исправление должно быть отдельной продуктовой задачей с сохранением блокировок и проверками конкуренции.

## Блокировки и риски

- В системе нет GNU Make, поэтому обязательные команды `make test` и `make verify DOCKER=1` не выполнены напрямую.
- Frontend тестовый образ не собирается из-за недоступного `frontend/node_modules` в Docker context, хотя каталог уже указан в `.dockerignore`; изменение Docker-контура без более широкого решения не выполнено.
- Отсутствуют Frontend JUnit/coverage и результат полного `make verify`; приложение не готово к слиянию или выпуску.
- Не покрытые этой итерацией конкурентные сценарии, rollback истории, полный отчёт/CSV, миграционная матрица и пользовательское поведение Frontend остаются незавершёнными критериями.
