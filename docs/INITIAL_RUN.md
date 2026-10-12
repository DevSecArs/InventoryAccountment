# Первоначальный запуск

Система уже содержит справочники, аутентификацию, поступления, синхронное проведение, историю и отчёты. Сначала выберите сценарий; команды разных окружений не смешивать.

## 1. Проверить тесты без установки Make и Node.js на хост

На Windows или Linux нужны Python и Docker с Linux-контейнерами:

~~~text
python scripts/build_test_image.py
docker compose -p inventory-tests-local -f compose.test-runner.yaml run --rm tests
docker compose -p inventory-tests-local -f compose.test-runner.yaml down --volumes

~~~

Это одноразовая PostgreSQL и тестовый контейнер без опубликованного UI. Подробности и отчёты — [UNIX_TESTS.md](UNIX_TESTS.md). Каждый новый исходный код требует новой сборки.

## 2. Открыть учебное приложение

В Unix shell с GNU Make, Python, Node.js 24/pnpm 11.19.0 и Docker Compose:

~~~bash
make setup DOCKER=1
make up DOCKER=1 DOCKER_RUN_ID=demo
make migrate DOCKER=1 DOCKER_RUN_ID=demo
make status DOCKER=1 DOCKER_RUN_ID=demo

~~~

Настройки берутся из .env.example: UI http://127.0.0.1:5174, API http://127.0.0.1:8001. API/UI публикуются на 0.0.0.0; PostgreSQL не публикуется. Это учебные учётные данные и удаляемый тестовый том, не рабочее хранилище.

Откройте UI и зарегистрируйте первого администратора в пустой БД. Затем создайте единицу СИ, материал и поставщика, черновик поступления, проведите его и получите отчёт. Через API можно задать несколько позиций и редактировать черновик; в текущей форме UI доступна одна позиция.

~~~bash
curl --fail http://127.0.0.1:8001/health/live
curl --fail http://127.0.0.1:8001/health/ready

~~~

Readiness проверяет соединение с PostgreSQL, но не наличие всех таблиц. При UndefinedTable выполнить миграции, а не создавать таблицы вручную. Интерактивный API — /docs; схема — /openapi.json.

Завершение с удалением только тестовых данных:

~~~bash
make down DOCKER=1 DOCKER_RUN_ID=demo

~~~

## 3. Запуск из исходников с внешней PostgreSQL

Backend читает /etc/InventoryAccountment/InventoryAccountment.env и переменные процесса (они имеют приоритет). Рабочий файл не создаётся make setup и не заменяется .env.example. В нём задаются DATABASE_URL, APP_ENV, APP_DEBUG; пример структуры:

~~~ini
DATABASE_URL=postgresql+psycopg2://<USER>:<PASSWORD>@<DB_HOST>:5432/inventory
APP_ENV=production
APP_DEBUG=false
APP_HOST=0.0.0.0
APP_PORT=8000

~~~

Замените плейсхолдеры, ограничьте права чтения группе сервиса. Реальный файл, пароли и дампы не сохранять в Git. Production использует Secure-cookie и требует HTTPS для браузерного входа.

В Unix shell после настройки PostgreSQL и инструментов:

~~~bash
make setup
make migrate
make run
make status

~~~

Make run использует Uvicorn и Vite в фоне; по умолчанию порты 8000/5173. Порты команд определяются переменными shell; APP_PORT только в файле Backend не меняет явно переданный Uvicorn --port. Логи/PID — reports/runtime/. Для службы и автозапуска используйте [systemd](SYSTEMD_SERVICE.md); обычный make run не создаёт systemd units.

Обычный make down останавливает фоновые процессы и обычный Compose, сохраняя его тома. Make up вместо make run переключает вас на Compose с собственной db; это не эквивалент перезапуска исходников с внешней БД.

## 4. Перед приёмкой

Обязателен make verify DOCKER=1, успешный CI актуального SHA и независимое одобрение. Отдельный test-образ не выполняет все этапы verify. Команды, известные ограничения проверки образа и побочный запуск make up после verify описаны в [GUIDE.md](../GUIDE.md).
