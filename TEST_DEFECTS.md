# Результаты тестирования MVP

## Docker-запуск для ручных проверок — 13 октября 2026 года

Задача без номера трекера: запуск PostgreSQL, миграций, API и UI на Windows
без Make и без установки Python/Node на хосте. Ветка codex/docker-manual-run.
Добавлены compose.manual.yaml и scripts/build_manual_images.ps1; инструкция
— [DOCKER_WINDOWS.md](docs/DOCKER_WINDOWS.md). Область — локальный учебный
стенд, без изменения бизнеса, схемы, основного Compose и CI.

Критические изменения для PR/MR:

- compose.manual.yaml: отдельный том, loopback-порты 8010/5180, запуск API
  после успешных миграций и проверка readiness; development-cookie для HTTP.
- scripts/build_manual_images.ps1: временный контекст по списку исходников,
  исключение зависимостей/.env/ссылок, проверка exit code Docker и очистка
  только созданного временного каталога. Общий .dockerignore не копируется,
  чтобы его правило reports не исключало frontend/src/features/reports.
- README.md: дополнительный интерфейс ручного запуска; обязательные проверки
  и пороги не заменяются и не меняются.

Фактические проверки в отдельном проекте inventory-manual-check:

1. PowerShell 5.1: сборщик завершился с кодом 0, временный контекст удалён.
2. Docker Compose config --quiet — успешно.
3. Frontend-образ: pnpm build (TypeScript + Vite) — успешно.
4. up -d --no-build --wait на чистой БД — код 0; migrate Exited (0),
   app/frontend/db healthy.
5. HTTP с Windows через localhost:5180: страница UI, readiness через прокси,
   регистрация, CSRF, создание/чтение единицы KG — успешно.
6. API readiness через localhost:8010 — успешно.
7. down без --volumes, повторный up --wait, вход прежним пользователем
   и чтение KG — успешно; данные сохранены.
8. Тестовый проект удалён через down --volumes; пользовательские проекты
   и данные не затрагивались. git diff --check — успешно.

Диагностический запрос из контейнера с Host frontend:5173 был отклонён
Vite (403); проверка выполнена по документированному адресу localhost,
защита Host не отключалась. Проверка UI по HTTP не является браузерной
демонстрацией всех действий пользователя.

Полный make verify, CI и сканирование образа в этой задаче не выполнялись;
GNU Make на Windows отсутствует. Unit/integration-набор бизнеса повторно
не запускался: проверялись новый контур запуска, миграции и HTTP-интеграция.
Это не подтверждение production-готовности или независимой приёмки.
Откат: остановить compose.manual.yaml без удаления тома и вернуть предыдущую
ревизию файлов. Схема этой задачей не меняется; будущие downgrade не выполнять
автоматически. PR/MR не создан; независимое одобрение остаётся необходимым.

## Исправление TS2322 и проверка 13 октября 2026 года

Задача без номера трекера: устранить отказ сборки из пользовательского лога
logs_13_10_2026_20_53.txt, сохранить отображение ошибки CSV и проверить весь
Linux test-контур. Исходный commit 8473eae, ветка codex/fix-report-error-render.
Критерий: boolean-условие в JSX, регрессия сообщения об ошибке экспорта,
успешные typecheck, тесты, сборка и миграции. Схема и данные не изменяются.

Причина: exportError имеет тип unknown; выражение через || и && могло
возвращать unknown как дочерний JSX-элемент. В ReportsPage.tsx проверяется
наличие ошибки через != null, а исходное значение передаётся ApiErrorNotice.
Добавлен тест отказа CSV с HTTP 503, сообщением и request_id, включая повторное
нажатие «Скачать CSV». В тестовом файле добавлен cleanup после каждого теста:
первый прогон новой регрессии выявил сохранение DOM предыдущих сценариев.
Этот промежуточный отказ исправлен; проверки не удалялись и пороги не менялись.

Команды (сборка и проверки завершились с exit code 0):

```text
python scripts/build_test_image.py
docker compose -p inventory-tests-report-fix-20261013 -f compose.test-runner.yaml run --rm --no-deps tests pnpm --dir frontend typecheck
docker compose -p inventory-tests-report-fix-20261013 -f compose.test-runner.yaml run --rm tests
docker compose -p inventory-tests-report-fix-20261013 -f compose.test-runner.yaml down --volumes
```

После добавления cleanup образ пересобран и полный прогон повторён;
TypeScript повторно проверен внутри frontend build.

| Проверка | Итог последнего прогона |
| --- | --- |
| Backend | 57 passed, 19 предупреждений об устаревающих API |
| Покрытие | 84,70%, порог 80% соблюдён |
| Frontend | 8 passed |
| TypeScript и Vite build | Успешно |
| Миграции | Успешно |
| Общая команда tests | Exit code 0 |

Проверенный образ inventory-accountment-tests:local:
sha256:057083a580b40dc54ceec864c22d5013cbc00b87b2fe16f3cbe45b37fdc3d793.
Лог: reports/unix-tests/report-fix-20261013.log; JUnit и coverage — в том же
каталоге. Собственный тестовый контейнер, сеть и том удалены; пользовательский
inventory-tests-local не изменялся. Образ сохранён для повторного запуска.

Полный make verify DOCKER=1 не выполнялся: GNU Make отсутствует на хосте,
а Linux test-образ не имеет Docker socket для полного контура. CI, SAST/audit,
mutation, backup/restore и сканирование образа этим прогоном не подтверждены.
Критический файл для независимой проверки: ReportsPage.test.tsx (новая
регрессия и изоляция DOM). Откат — возврат изменений страницы и теста,
пересборка образа; миграций нет. PR/MR не создан, независимая приёмка не заявляется.

Далее сохранены результаты предыдущих итераций; их количества тестов
и сведения о сборке не заменяют результаты от 13 октября выше.

## Состояние отчёта на 12 октября 2026 года

Описание сверено с исходниками 9701e9d. Числа ниже сохранены из предыдущих
прогонов: в задаче актуализации Markdown тесты повторно не запускались.
Текущая инвентаризация — [TEST_MATRIX.md](docs/TEST_MATRIX.md).
Полнота требований [TASK.md](TASK.md) пока не подтверждена.

## Актуализация после исправления блокировок

### Дополнение проверки отчётов

В текущей ветке добавлены интеграционные проверки JSON-отчёта и CSV: границы
`[from, to)`, исключение черновика, фильтр материала и точные суммы `Decimal`.
Проверка миграций теперь требует таблицу истории, её уникальное ограничение,
индекс и внешний ключ. Добавлены компонентные проверки страницы отчётов без
периода и с серверными строками/итогами.

Последний изолированный прогон `inventory-tests-final-20261012`:

- Backend: **57 passed**, coverage **84.70%**.
- Frontend: **7 passed**; TypeScript и production-сборка успешны.
- Миграции: успешны, включая обновление, downgrade/upgrade и Alembic check.

Тестовый контейнер, сеть и том после проверки удалены.

По отдельному поручению пользователя исправлен DEF-001 и подготовлен отдельный
Linux test-образ. Исторический отчёт ниже сохранён; его прежние блокировки и
утверждения о выполнении новых тестов уточняются результатами этого раздела.

- Блокировки Receipt, ReceiptItem и Material ограничены целевой таблицей через
  `FOR UPDATE OF`: eager LEFT JOIN больше не пытается блокировать nullable-сторону.
  Проверки статуса и транзакции сохранены. Миграций данных нет.
- Образ промежуточного прогона inventory-tests-fix-20261012 (55 Backend / 5 Frontend),
  `inventory-accountment-tests:local`, платформа `linux/amd64`, image ID
  `sha256:bfee5b49baf8357c599aeeeb90e3db86c8c3a7991a587e794e854f77aa309fff`.
- Образ включает Python, Node.js, pnpm, GNU Make и актуальные исходники/тесты.
  Контекст формируется без чтения локального node_modules; WSL-ссылки и реальные
  `.env` не передаются. Каталог исходников `features/reports` сохраняется.
- Vite читает переменные через `loadEnv`, без обращения к нетипизированному
  глобальному `process`; сборка интерфейса проверена в Linux.
- Новые регрессии: удаление черновика, конкурентное проведение с одной историей,
  неизменность updated_at при повторе, сохранность исходников отчётов в контексте.

Команды промежуточного прогона (55 Backend / 5 Frontend):

```text
python scripts/build_test_image.py
docker compose -p inventory-tests-fix-20261012 -f compose.test-runner.yaml run --rm tests
docker compose -p inventory-tests-fix-20261012 -f compose.test-runner.yaml down --volumes
```

Этот промежуточный запуск завершился с exit code 0:

| Проверка | Результат |
| --- | --- |
| Backend: актуальные unit и integration | 55 passed, 18 предупреждений об устаревающих API зависимостей |
| Покрытие Backend | 82,61%; порог 80% не изменялся |
| Frontend | 5 passed |
| TypeScript и production-сборка Frontend | Успешно |
| Alembic | Чистая БД, обновление, downgrade/upgrade последней ревизии и сравнение metadata — успешно |
| Ruff check/format изменённых Python-файлов | Успешно |
| git diff --check | Успешно |

Каталог артефактов переиспользуется последующими запусками; старый image ID
не приписывается последнему прогону 57/7. Пути отчётов промежуточного прогона: `reports/unix-tests/run.log`,
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

## Исторический baseline: контекст

Разделы ниже относятся к первоначальной проверке до исправлений.
DEF-001 уже исправлен; блокировка Windows-контекста обойдена отдельным
Linux test-образом. Утверждение U04–U05 passed в старой матрице было ошибочным:
эти файлы не вошли в старый образ. Их выполнение подтверждено позднейшими
прогонами выше. Статусы blocked/not run ниже не описывают текущий набор.


- Задача в трекере: отсутствует; источником требований служит `TASK.md`.
- Исходный commit: `faecb2a3a1cbc05b3958b8d087b36d549716c679`.
- Ветка: `codex/mvp-test-coverage`.
- Тестовый проект Docker: `inventory-accountment-local-terra-baseline-20261012`.
- Проверяемая миграция head: `a5b7c9d1e004`.
- Рабочие данные, production Compose и сторонние контейнеры не использовались.

## Исторический baseline: команды и результаты

| Команда | Exit code | Результат |
| --- | ---: | --- |
| `make test DOCKER=1 DOCKER_RUN_ID=terra-baseline-20261012` | 1 | Заблокирована: GNU Make отсутствует в Windows PATH. |
| `docker compose ... run app alembic upgrade head` | 0 | Миграции применены к изолированной PostgreSQL. |
| `docker compose ... run app pytest tests/unit tests/integration -xvv` | 1 | Собрано 45: 32 passed, 1 failed до `-x`; XML/JUnit записан в `reports/junit.xml`. |
| `docker compose ... run app pytest tests/unit -q` | 1 | 23 passed; тесты не обращались к DB-фикстурам. Exit 1 только из-за корректно сохранённого глобального порога coverage: 35.78% < 80%. |
| `pnpm --dir frontend test:run` | 1 | Локальный `vitest` недоступен как Windows executable. |
| `docker build --target frontend-test ...` | 1 | Docker не смог прочитать `frontend/node_modules`; стандартное исключение из `.dockerignore` не применяется к недоступной Windows-ссылке. |

Покрытие полного набора не получено: тестовый прогон закончен первым продуктовым дефектом. Имеющиеся артефакты backend: `reports/junit.xml`, `reports/coverage.xml`, `reports/htmlcov/`. Frontend JUnit и coverage отсутствуют из-за блокировки сборки test-образа.

## Исторический baseline: матрица проверок

| ID | Реализация | Результат |
| --- | --- | --- |
| U01–U03, U06 | `tests/unit/test_validation.py`, `test_password_verification.py` | passed в целевом прогоне до первого сбоя |
| U04–U05 | `tests/unit/test_supply_report.py` | passed в отдельном unit-прогоне |
| I01–I05 | существующие `tests/integration/test_api_catalogs.py` | passed в целевом прогоне |
| I06 | `tests/integration/test_receipts.py::test_receipt_draft_create_read_and_replace` | failed, DEF-001 |
| I09–I10, I13–I14 | `tests/integration/test_receipt_posting.py` | реализовано; blocked дефектом PATCH/блокировки в общем прогоне |
| I07–I08, I11–I17, C01–C06, R01–R04, M01–M06 | — | not run: не реализованы полностью в рамках текущего прогона |
| F01–F12 | — | blocked: frontend test-образ не собран |

## Исторический baseline: подтверждённый дефект

### DEF-001 — ошибка PostgreSQL при PATCH черновика (исправлен)

- Приоритет: высокий. Пользователь не может изменять созданный черновик; это нарушает I06 и согласованный сценарий `draft → posted`.
- Требование: `TASK.md`, I06; `docs/Техническое_задание.md`, создание и редактирование черновика.
- Минимальные данные: активные единица `KG`, поставщик `SUP`, материалы `M1` и `M2`, черновик `DOC-1` с одной строкой.
- Воспроизведение: выполнить `tests/integration/test_receipts.py::test_receipt_draft_create_read_and_replace` в изолированном Docker-контуре и отправить `PATCH /api/v1/receipts/{id}` с заменой строки.
- Ожидание: HTTP 200, черновик содержит новую строку.
- Факт: PostgreSQL возвращает `FOR UPDATE cannot be applied to the nullable side of an outer join`; HTTP-контракт не формируется.
- Падающий тест: `tests/integration/test_receipts.py::test_receipt_draft_create_read_and_replace`.
- Повторное воспроизведение: подтверждено подробным запуском `pytest ... -xvv`.
- Область: backend, `get_receipt_for_update`; исправление должно быть отдельной продуктовой задачей с сохранением блокировок и проверками конкуренции.

## Исторический baseline: блокировки и риски

- В системе нет GNU Make, поэтому обязательные команды `make test` и `make verify DOCKER=1` не выполнены напрямую.
- Frontend тестовый образ не собирается из-за недоступного `frontend/node_modules` в Docker context, хотя каталог уже указан в `.dockerignore`; изменение Docker-контура без более широкого решения не выполнено.
- Отсутствуют Frontend JUnit/coverage и результат полного `make verify`; приложение не готово к слиянию или выпуску.
- Не покрытые этой итерацией конкурентные сценарии, rollback истории, полный отчёт/CSV, миграционная матрица и пользовательское поведение Frontend остаются незавершёнными критериями.

## Оставшиеся ограничения

Полный make verify DOCKER=1 и CI этим отчётом не подтверждены. Два теста
ReportsPage проверяют отсутствие периода и серверные строки/итоги, но не
все ошибки экспорта, фильтры и инвалидацию кеша. UI поступлений не позволяет
редактировать сохранённый черновик или создать несколько строк; API умеет это.
Нет полной проверки rollback истории, конкурентного архивирования и
согласованности строк/итогов отчёта. Frontend coverage и E2E не настроены.
Эти ограничения не следует считать закрытыми по одному успешному набору.
