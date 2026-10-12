# InventoryAccountment как службы systemd

Текущий автоматизированный вариант описан в [DEPLOY_SCRIPT.md](DEPLOY_SCRIPT.md). Источник unit-файлов — функция ensure_systemd_units в deploy/deploy.sh; готовых unit-файлов в репозитории нет. Ниже их структура с настройками по умолчанию. Linux/systemd и доступная PostgreSQL требуются отдельно.

## Подготовка

Deploy-скрипт создаёт пользователя inv_acc, исходники /opt/InventoryAccountment, окружение venv и настройки /etc/InventoryAccountment/InventoryAccountment.env. Backend-зависимости он устанавливает через pip install из проекта, а не через uv.lock; это ограничение воспроизводимости рабочего развёртывания. Тестовый образ использует uv sync --frozen.

Системный env-файл читается Pydantic и передаётся Backend/migrate как EnvironmentFile. Права — только root и группа службы; реальные значения DATABASE_URL не выводить в отчёты. Переменные процесса имеют приоритет.

Для ручной подготовки сначала создайте пользователя и каталоги с подходящими владельцами, установите зависимости и примените миграции после backup. Не запускайте сервер с --reload. Используйте существующие проверенные ревизии; systemd не выполняет Git/CI-проверки.

## Миграции

Файл /etc/systemd/system/InventoryAccountment-migrate.service:

~~~ini
[Unit]
Description=InventoryAccountment database migrations
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=inv_acc
Group=inv_acc
WorkingDirectory=/opt/InventoryAccountment
EnvironmentFile=/etc/InventoryAccountment/InventoryAccountment.env
ExecStart=/opt/InventoryAccountment/venv/bin/python -m alembic upgrade head
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=full

~~~

Миграционный unit не включается в автозапуск. Выполнять его контролируемо:

~~~bash
sudo systemctl daemon-reload
sudo systemctl start InventoryAccountment-migrate.service
sudo systemctl status InventoryAccountment-migrate.service --no-pager

~~~

Head — a5b7c9d1e004. Это не разрешение автоматически понижать ревизию: downgrade последней миграции удаляет историю.

## Backend

Файл /etc/systemd/system/InventoryAccountment.service:

~~~ini
[Unit]
Description=InventoryAccountment API
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=inv_acc
Group=inv_acc
WorkingDirectory=/opt/InventoryAccountment
EnvironmentFile=/etc/InventoryAccountment/InventoryAccountment.env
ExecStart=/opt/InventoryAccountment/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target

~~~

Backend имеет аутентификацию и CSRF. Loopback по умолчанию выбран для проксирования и ограничения прямого доступа, а не из-за отсутствия входа. В production cookie Secure требует HTTPS. APP_HOST/APP_PORT в env-файле не заменяют явно переданные --host/--port.

## Frontend

Перед запуском установите зависимости frontend с pnpm 11.19.0 --frozen-lockfile и выполните pnpm build. Используйте Node.js одной ОС с node_modules. Deploy по умолчанию допускает Node >=22.13.0; Linux test-образ использует 24.21.0.

Файл /etc/systemd/system/InventoryAccountment-frontend.service:

~~~ini
[Unit]
Description=InventoryAccountment frontend preview
After=network-online.target InventoryAccountment.service
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=inv_acc
Group=inv_acc
WorkingDirectory=/opt/InventoryAccountment/frontend
ExecStart=/usr/bin/node /opt/InventoryAccountment/frontend/node_modules/vite/bin/vite.js preview --host 0.0.0.0 --port 4173
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target

~~~

В ручном unit замените /usr/bin/node фактическим абсолютным путём системного Node; deploy вычисляет его самостоятельно. Systemd не загружает nvm/pnpm из профиля пользователя. Vite проксирует /api и /health на 127.0.0.1:8000 по умолчанию. Для нестандартного BACKEND_PORT нужно отдельно задать VITE_API_PROXY_TARGET frontend-службе: deploy пока не добавляет его в unit.

Vite preview на HTTP не настраивает HTTPS и не является production Nginx. Для удалённого браузерного входа при APP_ENV=production нужен отдельно настроенный TLS reverse proxy; health-check по HTTP сам по себе это не проверяет.

## Управление и диагностика

~~~bash
sudo systemctl daemon-reload
sudo systemctl enable --now InventoryAccountment.service InventoryAccountment-frontend.service
sudo systemctl status InventoryAccountment.service InventoryAccountment-frontend.service --no-pager
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready
sudo journalctl -u InventoryAccountment.service -n 100 --no-pager
sudo journalctl -u InventoryAccountment-frontend.service -n 100 --no-pager

~~~

После изменения unit нужен daemon-reload; после кода/env — restart. После обновления UI сначала pnpm build, затем restart frontend. Restart=on-failure перезапускает через 5 секунд, StartLimit ограничивает цикл. После устранения причины исчерпания лимита:

~~~bash
sudo systemctl reset-failed InventoryAccountment.service
sudo systemctl restart InventoryAccountment.service

~~~

При 203/EXEC проверить доступ пользователя службы к исполняемому файлу, права прохода по каталогам и опцию noexec:

~~~bash
sudo -u inv_acc /opt/InventoryAccountment/venv/bin/python --version
namei -l /opt/InventoryAccountment/venv/bin/python
findmnt -no OPTIONS -T /opt/InventoryAccountment

~~~

Остановка — systemctl stop соответствующих служб; make down ими не управляет. Настройки сети — [FIREWALL.md](FIREWALL.md). Живая проверка этих units в данной актуализации не выполнялась.
