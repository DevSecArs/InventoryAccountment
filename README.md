# InventoryAccountment — складской учёт

MVP одного склада: единицы измерения, материалы, поставщики, поступления, синхронное проведение, история статусов и отчёт по поставкам с CSV. Backend — FastAPI, SQLAlchemy и PostgreSQL; Frontend — React/TypeScript и Vite. RabbitMQ, outbox и фоновые обработчики в согласованный MVP не входят.

## Текущее состояние

Сверено с исходниками ревизии 9701e9d. API поддерживает многопозиционные черновики, PATCH, удаление, переход draft → posted и безопасный повтор проведения. История хранится в PostgreSQL; отчёт включает только posted, количества передаются десятичными строками.

В браузере работают вход, профиль, справочники, список/создание/удаление/проведение поступлений, просмотр истории и отчёт/CSV. Форма поступления пока создаёт одну строку; редактирование сохранённого черновика и остальные фильтры списка доступны через API, но не реализованы в UI. Администрирование показывает health-проверки; API управления пользователями, backup и мониторингом отсутствуют.

По последнему сохранённому [отчёту](TEST_DEFECTS.md): 57 Backend-тестов, 7 Frontend-тестов, покрытие Backend 84,70%, сборка Frontend и миграционные проверки прошли. Это результат конкретного предыдущего прогона, а не нового запуска или успешного CI. Полный make verify, CD и человеческая приёмка не подтверждены.

## Документация

- [Техническое задание и ограничения MVP](docs/Техническое_задание.md)
- [Первоначальный запуск](docs/INITIAL_RUN.md)
- [Команды и диагностика](GUIDE.md)
- [API](docs/API.md)
- [Frontend: запуск](frontend/README.md) и [требования к интерфейсу](docs/WEB_UI_CODEX_SPEC.md)
- [Linux-образ тестов](docs/UNIX_TESTS.md), [матрица тестов](docs/TEST_MATRIX.md), [задание на расширение тестов](TASK.md)
- [Ubuntu](docs/UBUNTU_DEPLOYMENT.md), [systemd](docs/SYSTEMD_SERVICE.md), [скрипт развёртывания](docs/DEPLOY_SCRIPT.md), [сеть и firewall](docs/FIREWALL.md)
- [Правила репозитория](AGENTS.md) и [настройки GitHub](.github/README.md)

## Структура

~~~text
app/
  main.py                     # импорт приложения
  http.py                     # FastAPI, health, ошибки, подключение роутеров
  postgresql.py               # engine, сессии, транзакции
  entities/
    routers.py                # маршруты /api/v1
    auth.py                   # пользователи, сессии и проверки доступа
    unit.py, material.py, supplier.py
    receipt.py                # поступление, строки и проведение
    receipt_item.py           # совместимый переэкспорт модели строки
    receipt_status_history.py
    supply_report.py          # вычисляемый отчёт и CSV
alembic/versions/              # миграции; head a5b7c9d1e004
frontend/src/                 # React-приложение и компонентные тесты
tests/unit/, tests/integration/
scripts/                      # проверки, backup/restore, сборщик test-образа
deploy/                       # развёртывание из исходников на Ubuntu

~~~

HTTP-слой использует модели и операции сущностей; сущности используют общий модуль PostgreSQL. Сессия выполняет commit/rollback через session_scope; маршрут проведения дополнительно фиксирует транзакцию до формирования успешного ответа. Отдельные repository/service-слои отсутствуют.

## Ручной запуск на Windows без Make

Нужны Docker Desktop (Linux containers) и PowerShell. Из корня репозитория:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build_manual_images.ps1
docker compose -f compose.manual.yaml up -d --no-build --wait
```

После успешной сборки и запуска откройте http://localhost:5180.
PostgreSQL, миграции, API и UI работают в Docker. Данные сохраняются после
остановки. Команды остановки, обновления и диагностики — в
[краткой инструкции](docs/DOCKER_WINDOWS.md).

## Быстрая проверка на Windows или Linux

Нужны Python и Docker с Linux-контейнерами. GNU Make, Node.js и зависимости тестов устанавливаются внутри отдельного образа:

~~~text
python scripts/build_test_image.py
docker compose -p inventory-tests-local -f compose.test-runner.yaml run --rm tests
docker compose -p inventory-tests-local -f compose.test-runner.yaml down --volumes

~~~

Сборку повторять после изменения кода или тестов. Отчёты — reports/unix-tests/. Этот контур не публикует порты и не заменяет полный make verify.

## Запуск учебного приложения через Make

Makefile рассчитан на Unix shell. Для него нужны Git, GNU Make, Python, Node.js/pnpm и Docker Compose; версии и подготовка описаны в [GUIDE.md](GUIDE.md). Не запускать эти команды в обычном PowerShell без совместимого окружения.

~~~bash
make setup DOCKER=1
make up DOCKER=1 DOCKER_RUN_ID=local-demo
make migrate DOCKER=1 DOCKER_RUN_ID=local-demo
make status DOCKER=1 DOCKER_RUN_ID=local-demo
# После завершения: удаляет тестовые данные этого проекта
make down DOCKER=1 DOCKER_RUN_ID=local-demo

~~~

Тестовый Make-контур использует .env.example: Frontend 5174, API 8001, PostgreSQL без опубликованного порта. UI/API слушают 0.0.0.0. Обычный Compose использует системный файл /etc/InventoryAccountment/InventoryAccountment.env, API-порт APP_PORT, Frontend 5173 по умолчанию и БД на loopback:5433. Это разные режимы; обычный make down сохраняет тома, DOCKER=1 удаляет тестовые тома.

Для запуска из исходников make run запускает Uvicorn и Vite в фоне, с логами и PID в reports/runtime/. Настройки Backend читаются из системного файла или переменных процесса. Без DOCKER=1 команда make migrate работает с DATABASE_URL напрямую.

## Проверки и известные ограничения доставки

Основная обязательная команда перед слиянием — make verify DOCKER=1. Она выполняет lock-check, quality, тесты, mutation, миграции, backup/restore, container-smoke, проверку очистки и Git diff. Backend-порог покрытия — 80%; Frontend-порог в текущей конфигурации отсутствует.

В Makefile container-smoke пока передаёт Trivy фиксированный тег inventory-accountment-local-ubuntu-verify-app:latest, а не получает ID текущего контейнера. Поэтому совпадение проверенного и просканированного образа нельзя считать гарантированным; требование проверки одного image ID сохраняется. Сам smoke проверяет health, регистрацию и создание/чтение единицы, а не полный сценарий поступлений.

После успешного verify выполняется make up с исходным DOCKER. Для безопасного тестирования передавать DOCKER=1 и выполнять финальную очистку своего проекта. Make test не пересобирает существующий backend-образ автоматически: перед проверкой изменённых тестов/кода нужен актуальный образ.

GitHub Actions вызывает make setup DOCKER=1 и make verify DOCKER=1, выгружает reports/ даже при ошибке. Наличие workflow не подтверждает его успешный запуск. Отдельного CD по digest, Nginx/TLS-конфигурации и мониторинга в репозитории нет; обычный Compose запускает Vite dev-сервер.

## Разработка и приёмка

Обязательная цепочка: задача → код → локальные проверки → Git → CI → образ → CD → проверка релиза → наблюдение. Изменения — в отдельной ветке, для агента с префиксом codex/. До слияния нужны успешные обязательные проверки актуального коммита и независимое одобрение; их нельзя заменять локальной самооценкой.

Изменения README, ТЗ, тестов, Make/Docker/CI, миграций и эксплуатации перечисляются в PR/MR с причиной и влиянием на приёмку. Проверки, пороги и требования не ослаблять для получения успешного результата. Финальная приёмка требует живой демонстрации и контрольного изменения по цепочке либо контролируемого отказа с восстановлением; подтверждения сохраняются в задаче/релизе.

Формат коммита: [TAG] краткое описание на русском. Используемые теги: [ADD] — добавление, [FIX] — исправление, [IMP] — улучшение, [REF] — рефакторинг, [TEST] — тесты, [REM] — удаление, [MOV] — перенос, [REV] — откат, [REL] — релиз, [I18N] — локализация, [PERF] — производительность, [CLN] — очистка, [LINT] — форматирование. Подробности при необходимости добавляются отдельным абзацем тела коммита.
