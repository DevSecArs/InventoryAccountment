# InventoryAccountment как служба systemd

Краткая инструкция для запуска текущего API напрямую из исходного кода на
Linux, без Docker. PostgreSQL должна быть уже установлена и доступна отдельно.

API пока не имеет аутентификации, поэтому служба по умолчанию слушает только
`127.0.0.1`. Не открывайте порт во внешнюю сеть.

## 1. Подготовить исходный код

Нужны Linux с `systemd`, Python 3.11+ и PostgreSQL. Выполните команды от
администратора; `<URL_РЕПОЗИТОРИЯ>` замените адресом репозитория.

```bash
sudo useradd --system --home /opt/InventoryAccountment --shell /usr/sbin/nologin inv_acc
sudo -u inv_acc git clone <URL_РЕПОЗИТОРИЯ> /opt/InventoryAccountment
sudo -u inv_acc python3.11 -m venv /opt/InventoryAccountment/venv
sudo -u inv_acc /opt/InventoryAccountment/venv/bin/pip install /opt/InventoryAccountment
```

При обновлении используйте проверенную ревизию исходного кода и повторите
установку зависимостей. Не используйте `--reload`: он нужен только при
разработке.

## 2. Создать отдельный файл настроек

Настройки и пароль к БД не хранятся рядом с исходным кодом. Создайте каталог и
файл, доступный только root и пользователю службы:

```bash
sudo install -d -m 750 -o root -g inv_acc /etc/InventoryAccountment
sudoedit /etc/InventoryAccountment/InventoryAccountment.env
sudo chown root:inv_acc /etc/InventoryAccountment/InventoryAccountment.env
sudo chmod 640 /etc/InventoryAccountment/InventoryAccountment.env
```

В открывшемся файле укажите свои значения:

```ini
DATABASE_URL=postgresql+psycopg2://username:CHANGE_ME@db_host:5432/db_name
APP_ENV=production
APP_DEBUG=false
APP_HOST=127.0.0.1
APP_PORT=8000
```

Формат файла — `ИМЯ=ЗНАЧЕНИЕ`; не добавляйте пробелы вокруг `=`. Файл находится
в `/etc`, не попадает в Git и используется и API, и миграциями.

## 3. Применить миграции

Перед миграцией рабочей БД создайте проверенную резервную копию. Создайте
`/etc/systemd/system/InventoryAccountment-migrate.service`:

```ini
[Unit]
Description=InventoryAccountment database migrations
After=network-online.target postgresql.service
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
```

Если PostgreSQL работает на другом хосте, удалите `postgresql.service` из
строки `After=`. Затем выполните:

```bash
sudo systemctl daemon-reload
sudo systemctl start InventoryAccountment-migrate.service
sudo systemctl status InventoryAccountment-migrate.service --no-pager
```

Не включайте unit миграций в автозапуск: изменение схемы должно быть отдельным
контролируемым действием.

Если unit завершается с `status=203/EXEC` и `Permission denied`, проверьте
запуск от имени пользователя службы:

```bash
sudo -u inv_acc /opt/InventoryAccountment/venv/bin/python -m alembic --version
namei -l /opt/InventoryAccountment/venv/bin/python
findmnt -no OPTIONS -T /opt/InventoryAccountment
```

У пользователя `inv_acc` должно быть право прохода (`x`) для всех каталогов
в пути. Опция монтирования `noexec` для `/opt` также запрещает запуск файлов;
в таком случае разместите виртуальное окружение на файловой системе без
`noexec` или измените настройку монтирования по правилам администратора.

## 4. Создать и включить API

Создайте `/etc/systemd/system/InventoryAccountment.service`:

```ini
[Unit]
Description=InventoryAccountment API
After=network-online.target postgresql.service
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
```

Загрузите конфигурацию, запустите службу и включите автозапуск:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now InventoryAccountment.service
sudo systemctl status InventoryAccountment.service --no-pager
```

## Автоматический перезапуск после сбоя

Параметры `Restart=on-failure` и `RestartSec=5` в unit выше уже включают
автоматический запуск через 5 секунд, если процесс API завершился с ошибкой.
`StartLimitBurst=5` ограничивает число таких запусков пятью за 60 секунд, чтобы
не создавать бесконечный цикл при постоянной ошибке.

Если вы добавили эти строки в уже существующий unit, примените изменения:

```bash
sudo systemctl daemon-reload
sudo systemctl restart InventoryAccountment.service
```

Проверьте настройку и причину перезапусков:

```bash
sudo systemctl show InventoryAccountment.service -p Restart -p RestartUSec -p NRestarts
sudo journalctl -u InventoryAccountment.service -n 100 --no-pager
```

После исправления ошибки, которая исчерпала лимит запусков, снимите состояние
ошибки и запустите службу вручную:

```bash
sudo systemctl reset-failed InventoryAccountment.service
sudo systemctl start InventoryAccountment.service
```

## 5. Проверить и управлять

```bash
# API и соединение с БД
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready

# Запуск, остановка, перезапуск
sudo systemctl start InventoryAccountment.service
sudo systemctl stop InventoryAccountment.service
sudo systemctl restart InventoryAccountment.service

# Статус и журнал
sudo systemctl status InventoryAccountment.service --no-pager
sudo journalctl -u InventoryAccountment.service -f

# Отключить автозапуск
sudo systemctl disable InventoryAccountment.service
```

После изменения unit-файла выполните `sudo systemctl daemon-reload`; после
изменения исходного кода или файла настроек —
`sudo systemctl restart InventoryAccountment.service`.

`/health/live` проверяет, что API запущено, а `/health/ready` — также
доступность PostgreSQL. Если ready-проверка не проходит, проверьте
`DATABASE_URL`, доступность БД и результат unit миграций.

## Frontend: локальный запуск и systemd

### Установка Node.js и сопутствующих пакетов

Для локальной разработки установите Node.js `>=22.13.0` и pnpm `11.19.0`,

Скачайте и установите nvm:

`curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.7/install.sh | bash`

вместо перезапуска оболочки выполните

`\. "$HOME/.nvm/nvm.sh"`

Скачайте и установите Node.js:

`nvm install 24`

Проверьте версию Node.js:

`node -v # Should print "v24.21.0".`

Проверьте версию npm :

`npm -v # Should print "11.19.0".`

Установите pnpm:

`npx get-pnpm`

Обновите переменные среды:

`source /home/inv_acc/.bashrc`

### Установка зависимостей и запуск

затем выполните из корня репозитория:

```bash
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

Откройте `http://127.0.0.1:5173`. Dev-сервер автоматически направляет запросы
`/api` и `/health` к API на `127.0.0.1:8000`. Остановить его можно сочетанием
`Ctrl+C`.

Для запуска frontend через systemd сначала соберите его от имени пользователя
службы. `pnpm` нужен для установки зависимостей и сборки, но не используется
в `ExecStart`: systemd не загружает пользовательский профиль, в котором pnpm
может быть доступен.

```bash
cd /opt/InventoryAccountment/frontend && pnpm install --frozen-lockfile && pnpm build
sudo -u inv_acc /usr/bin/node --version
sudo -u inv_acc test -f /opt/InventoryAccountment/frontend/node_modules/vite/bin/vite.js && echo "Vite найден"
```

Создайте `/etc/systemd/system/InventoryAccountment-frontend.service`:

```ini
[Unit]
Description=InventoryAccountment frontend preview
After=network-online.target InventoryAccountment.service
Wants=network-online.target

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
```

Запустите и включите автозапуск:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now InventoryAccountment-frontend.service
sudo systemctl status InventoryAccountment-frontend.service --no-pager
```

Frontend будет доступен на `http://<IP_СЕРВЕРА>:4173` и перезапустится через
пять секунд после аварийного завершения. Путь запуска использует системный
Node.js `/usr/bin/node` и Vite из
`/opt/InventoryAccountment/frontend/node_modules`, поэтому не зависит от пути
pnpm в домашнем каталоге пользователя. После изменения frontend повторите
`pnpm build` и выполните
`sudo systemctl restart InventoryAccountment-frontend.service`.

Если frontend должен быть доступен только на самом сервере, замените
`--host 0.0.0.0` в `ExecStart` на `--host 127.0.0.1`. При внешнем доступе
откройте порт `4173` в firewall только для доверенной сети клиентов:

```bash
sudo ufw allow from <CLIENT_NETWORK> to any port 4173 proto tcp
```

`vite preview` пригоден для локального или учебного стенда. Для публичного
production-доступа раздавайте собранный каталог `frontend/dist` через Nginx
по HTTPS, а Vite оставляйте на loopback-интерфейсе.

## Проверка документации

Проверьте формат изменений командой `git diff --check`. `make verify` сейчас
недоступен, поскольку в проекте нет Makefile.
