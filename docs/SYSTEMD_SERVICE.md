# InventoryAccountment как служба systemd

Краткая инструкция для запуска текущего API напрямую из исходного кода на
Linux, без Docker. PostgreSQL должна быть уже установлена и доступна отдельно.

API пока не имеет аутентификации, поэтому служба по умолчанию слушает только
`127.0.0.1`. Не открывайте порт во внешнюю сеть.

## 1. Подготовить исходный код

Нужны Linux с `systemd`, Python 3.11+ и PostgreSQL. Выполните команды от
администратора; `<URL_РЕПОЗИТОРИЯ>` замените адресом репозитория.

```bash
sudo useradd --system --home /opt/inventory-accountment --shell /usr/sbin/nologin inventory
sudo -u inventory git clone <URL_РЕПОЗИТОРИЯ> /opt/inventory-accountment
sudo -u inventory python3.11 -m venv /opt/inventory-accountment/venv
sudo -u inventory /opt/inventory-accountment/venv/bin/pip install /opt/inventory-accountment
```

При обновлении используйте проверенную ревизию исходного кода и повторите
установку зависимостей. Не используйте `--reload`: он нужен только при
разработке.

## 2. Создать отдельный файл настроек

Настройки и пароль к БД не хранятся рядом с исходным кодом. Создайте каталог и
файл, доступный только root и пользователю службы:

```bash
sudo install -d -m 750 -o root -g inventory /etc/inventory-accountment
sudoedit /etc/inventory-accountment/inventory-accountment.env
sudo chown root:inventory /etc/inventory-accountment/inventory-accountment.env
sudo chmod 640 /etc/inventory-accountment/inventory-accountment.env
```

В открывшемся файле укажите свои значения:

```ini
DATABASE_URL=postgresql+psycopg2://inventory:CHANGE_ME@127.0.0.1:5432/inventory
APP_ENV=production
APP_DEBUG=false
APP_HOST=127.0.0.1
APP_PORT=8000
```

Формат файла — `ИМЯ=ЗНАЧЕНИЕ`; не добавляйте пробелы вокруг `=`. Файл находится
в `/etc`, не попадает в Git и используется и API, и миграциями.

## 3. Применить миграции

Перед миграцией рабочей БД создайте проверенную резервную копию. Создайте
`/etc/systemd/system/inventory-accountment-migrate.service`:

```ini
[Unit]
Description=InventoryAccountment database migrations
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=oneshot
User=inventory
Group=inventory
WorkingDirectory=/opt/inventory-accountment
EnvironmentFile=/etc/inventory-accountment/inventory-accountment.env
ExecStart=/opt/inventory-accountment/venv/bin/python -m alembic upgrade head
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=full
```

Если PostgreSQL работает на другом хосте, удалите `postgresql.service` из
строки `After=`. Затем выполните:

```bash
sudo systemctl daemon-reload
sudo systemctl start inventory-accountment-migrate.service
sudo systemctl status inventory-accountment-migrate.service --no-pager
```

Не включайте unit миграций в автозапуск: изменение схемы должно быть отдельным
контролируемым действием.

Если unit завершается с `status=203/EXEC` и `Permission denied`, проверьте
запуск от имени пользователя службы:

```bash
sudo -u inventory /opt/inventory-accountment/venv/bin/python -m alembic --version
namei -l /opt/inventory-accountment/venv/bin/python
findmnt -no OPTIONS -T /opt/inventory-accountment
```

У пользователя `inventory` должно быть право прохода (`x`) для всех каталогов
в пути. Опция монтирования `noexec` для `/opt` также запрещает запуск файлов;
в таком случае разместите виртуальное окружение на файловой системе без
`noexec` или измените настройку монтирования по правилам администратора.

## 4. Создать и включить API

Создайте `/etc/systemd/system/inventory-accountment.service`:

```ini
[Unit]
Description=InventoryAccountment API
After=network-online.target postgresql.service
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=inventory
Group=inventory
WorkingDirectory=/opt/inventory-accountment
EnvironmentFile=/etc/inventory-accountment/inventory-accountment.env
ExecStart=/opt/inventory-accountment/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
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
sudo systemctl enable --now inventory-accountment.service
sudo systemctl status inventory-accountment.service --no-pager
```

## Автоматический перезапуск после сбоя

Параметры `Restart=on-failure` и `RestartSec=5` в unit выше уже включают
автоматический запуск через 5 секунд, если процесс API завершился с ошибкой.
`StartLimitBurst=5` ограничивает число таких запусков пятью за 60 секунд, чтобы
не создавать бесконечный цикл при постоянной ошибке.

Если вы добавили эти строки в уже существующий unit, примените изменения:

```bash
sudo systemctl daemon-reload
sudo systemctl restart inventory-accountment.service
```

Проверьте настройку и причину перезапусков:

```bash
sudo systemctl show inventory-accountment.service -p Restart -p RestartUSec -p NRestarts
sudo journalctl -u inventory-accountment.service -n 100 --no-pager
```

После исправления ошибки, которая исчерпала лимит запусков, снимите состояние
ошибки и запустите службу вручную:

```bash
sudo systemctl reset-failed inventory-accountment.service
sudo systemctl start inventory-accountment.service
```

## 5. Проверить и управлять

```bash
# API и соединение с БД
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready

# Запуск, остановка, перезапуск
sudo systemctl start inventory-accountment.service
sudo systemctl stop inventory-accountment.service
sudo systemctl restart inventory-accountment.service

# Статус и журнал
sudo systemctl status inventory-accountment.service --no-pager
sudo journalctl -u inventory-accountment.service -f

# Отключить автозапуск
sudo systemctl disable inventory-accountment.service
```

После изменения unit-файла выполните `sudo systemctl daemon-reload`; после
изменения исходного кода или файла настроек —
`sudo systemctl restart inventory-accountment.service`.

`/health/live` проверяет, что API запущено, а `/health/ready` — также
доступность PostgreSQL. Если ready-проверка не проходит, проверьте
`DATABASE_URL`, доступность БД и результат unit миграций.

## Проверка документации

Проверьте формат изменений командой `git diff --check`. `make verify` сейчас
недоступен, поскольку в проекте нет Makefile.
