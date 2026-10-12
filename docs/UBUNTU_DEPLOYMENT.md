# Развёртывание на Ubuntu: текущие варианты

Документ сверяется с кодом, но не подтверждает проведённое развёртывание на сервере. Различайте учебный запуск, проверку и production-доставку: в репозитории есть Compose и deploy-скрипт, но нет CD по digest и Nginx/TLS-конфигурации.

## 1. Подготовка

Нужны Ubuntu с доступом к Git/Docker Hub/PyPI/npm, Git, Python 3.11+, GNU Make, Node.js 24 и pnpm 11.19.0. Docker Engine/Compose должны быть доступны пользователю. Make setup вызывает scripts/ensure_docker.sh, который при отсутствии Docker может установить его на Ubuntu; после добавления в docker-группу нужен новый сеанс.

Проверьте инструменты:

~~~bash
git --version
python3 --version
make --version
node --version
pnpm --version
docker version
docker compose version

~~~

Получите чистую копию нужной ветки/ревизии, проверьте git status. Для выпуска нужен одобренный SHA, а не просто последнее состояние main/dev. Установку ОС и внешних репозиториев выполняет администратор; эта инструкция не считает её уже выполненной.

## 2. Изолированная проверка

~~~bash
make setup DOCKER=1
make verify DOCKER=1 DOCKER_RUN_ID=ubuntu-verify BASE_REF=origin/main

~~~

BASE_REF должен существовать; при другой базовой ветке укажите её. Verify включает качество, тесты, миграции, backup/restore и контейнерную проверку; при отказе не продолжать выпуск и не ослаблять проверки.

Известное ограничение: container-smoke сканирует фиксированный тег inventory-accountment-local-ubuntu-verify-app:latest. Для других DOCKER_RUN_ID это может оказаться отсутствующим или чужим образом. Даже совпадение имени не заменяет проверку одного image ID. Полный verify на актуальном коммите здесь не подтверждён.

После успешного verify тестовый Compose снова запущен через make up DOCKER=1. Посмотрите логи и затем удалите только этот проект:

~~~bash
make status DOCKER=1 DOCKER_RUN_ID=ubuntu-verify
make down DOCKER=1 DOCKER_RUN_ID=ubuntu-verify

~~~

Если нужен только набор тестов без Make/Node на хосте, используйте [Linux test-образ](UNIX_TESTS.md). Его успех не заменяет verify.

## 3. Учебный стенд

~~~bash
make up DOCKER=1 DOCKER_RUN_ID=ubuntu-demo
make migrate DOCKER=1 DOCKER_RUN_ID=ubuntu-demo

~~~

UI — http://<SERVER_IP>:5174, API — :8001, данные тестовые и удаляются make down DOCKER=1. В .env.example APP_ENV=test, поэтому cookie не Secure. Такой режим предназначен для закрытого учебного окружения, не для production.

## 4. Запуск с рабочей БД из исходников

Для длительно работающего экземпляра используйте [deploy-скрипт](DEPLOY_SCRIPT.md) и [systemd](SYSTEMD_SERVICE.md). Он создаёт пользователя, venv, units и системный env-файл; PostgreSQL уже должна существовать. Перед применением миграций нужна проверенная копия именно рабочей БД.

При ручной подготовке настройки лежат в /etc/InventoryAccountment/InventoryAccountment.env:

~~~ini
DATABASE_URL=postgresql+psycopg2://<USER>:<PASSWORD>@<DB_HOST>:5432/inventory
APP_ENV=production
APP_DEBUG=false
APP_PORT=8000

~~~

Создайте файл редактором, назначьте права root/группе службы; не коммитьте его. Не копируйте тестовый .env.example. Без systemd команды make migrate и make run используют исходники; make run запускает Uvicorn и Vite в фоне. Для настройки портов Make использует окружение shell, а не автоматически все значения системного env-файла.

APP_ENV=production включает Secure-cookie. Для браузерного входа по удалённому адресу нужен HTTPS, который репозиторий не настраивает. Vite preview — учебный сервер, не готовая production-раздача.

## 5. Обычный Compose

Make up без DOCKER=1 использует docker-compose.yaml и системный env-файл. Он поднимает db, runtime API и Vite dev-сервер. Помимо DATABASE_URL нужны APP_ENV/APP_DEBUG/APP_PORT и настройки POSTGRES_*; Frontend-порт по умолчанию 5173.

DATABASE_URL внутри app должна указывать на доступную контейнеру БД. Если это сервис db, хост — db и порт 5432, а не опубликованный на хосте 5433. PostgreSQL публикуется только на 127.0.0.1; API и UI — на 0.0.0.0. Применить миграции именно к этому окружению можно через:

~~~bash
docker compose --project-name inventory-accountment --env-file /etc/InventoryAccountment/InventoryAccountment.env -f docker-compose.yaml run --rm app alembic upgrade head

~~~

Обычный make migrate запускает Alembic на хосте; контейнерный hostname db с хоста может не разрешаться. Не смешивайте два способа запуска.

## 6. Проверка, backup и откат

Health/live и health/ready должны отвечать status=ok; затем проверьте авторизацию и реальный сценарий поступления/истории/отчёта. Ready не проверяет миграции. Наличие отчётных файлов не равно успешной проверке: нужны содержимое, exit code, SHA и идентификатор образа.

Make backup обращается к сервису db выбранного Compose. Если DATABASE_URL приложения указывает на внешнюю PostgreSQL, этот backup не покрывает её автоматически. Для внешней БД нужен отдельный проверенный механизм PostgreSQL backup/restore. Восстановление сначала выполняется в изолированной БД.

Перед обновлением: резервная копия → проверенный SHA → проверки → проверка совместимости схемы → миграции → перезапуск выбранного режима → health и сквозной сценарий. Не подменять make run на make up при обычном перезапуске: это разные окружения.

Откат приложения возможен только с совместимой схемой. Downgrade a5b7c9d1e004 удаляет историю статусов, поэтому не выполнять его на рабочей БД без отдельного разрешения/плана. Независимое одобрение, CI, проверка образа, CD и живая приёмка остаются обязательными; ни одна инструкция не подтверждает их автоматически.
