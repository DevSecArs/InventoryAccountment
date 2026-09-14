# Настройка firewall для API и PostgreSQL

Инструкция рассчитана на два сервера с Ubuntu и UFW:

```text
Клиенты → app-server:8000 → db-server:5432
```

Клиенты подключаются только к API на `app-server`. PostgreSQL на `db-server`
принимает соединения только от `app-server`. Используйте частные адреса сети,
а не публикуйте PostgreSQL в интернет.

В командах замените значения:

- `<CLIENT_NETWORK>` — доверенная сеть клиентов, например `10.10.0.0/24`;
- `<APP_SERVER_IP>` — частный IP сервера API, например `10.20.0.10`;
- `<DB_SERVER_IP>` — частный IP сервера PostgreSQL, например `10.20.0.20`;
- `<SSH_NETWORK>` — сеть администраторов, например `10.10.1.0/24`.

Перед включением UFW откройте доступ по SSH из `<SSH_NETWORK>`, иначе можно
потерять доступ к серверу. Выполняйте настройку через консоль провайдера или
из второй SSH-сессии, чтобы сразу проверить соединение.

## 1. Открыть API для клиентов

По умолчанию unit из инструкции systemd слушает `127.0.0.1`, поэтому клиенты
его не видят. Если клиенты должны обращаться к FastAPI напрямую, на
`app-server` измените `ExecStart` в
`/etc/systemd/system/inventory-accountment.service`:

```ini
ExecStart=/opt/inventory-accountment/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Примените изменение:

```bash
sudo systemctl daemon-reload
sudo systemctl restart inventory-accountment.service
```

Откройте только SSH для администраторов и API для сети клиентов:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from <SSH_NETWORK> to any port 22 proto tcp
sudo ufw allow from <CLIENT_NETWORK> to any port 8000 proto tcp
sudo ufw enable
sudo ufw status numbered
```

Не используйте правило `ufw allow 8000`: оно откроет API всем адресам. В
текущем приложении нет аутентификации, поэтому ограничение доверенной сетью
обязательно. Если перед API установлен reverse proxy, вместо порта `8000`
откройте для клиентов только его HTTPS-порт `443`, а Uvicorn оставьте на
`127.0.0.1`.

## 2. Закрыть PostgreSQL для клиентов

На `db-server` PostgreSQL должен слушать только частный адрес. В
`postgresql.conf` укажите:

```ini
listen_addresses = '<DB_SERVER_IP>'
```

В `pg_hba.conf` разрешите доступ к базе только для пользователя приложения с
IP `app-server`:

```text
host    inventory    inventory    <APP_SERVER_IP>/32    scram-sha-256
```

Путь к этим файлам зависит от версии PostgreSQL. Узнать его можно командой:

```bash
sudo -u postgres psql -c 'SHOW config_file;'
sudo -u postgres psql -c 'SHOW hba_file;'
```

Перезапустите PostgreSQL после изменения конфигурации:

```bash
sudo systemctl restart postgresql
```

Затем на `db-server` включите firewall. Он разрешает порт PostgreSQL только
одному серверу приложения:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow from <SSH_NETWORK> to any port 22 proto tcp
sudo ufw allow from <APP_SERVER_IP> to any port 5432 proto tcp
sudo ufw enable
sudo ufw status numbered
```

## 3. Указать БД в настройках приложения

На `app-server` в
`/etc/inventory-accountment/inventory-accountment.env` укажите приватный адрес
сервера БД:

```ini
DATABASE_URL=postgresql+psycopg2://inventory:<PASSWORD>@<DB_SERVER_IP>:5432/inventory
```

После изменения настроек перезапустите API:

```bash
sudo systemctl restart inventory-accountment.service
```

## 4. Проверить доступ

На `app-server`:

```bash
curl --fail http://127.0.0.1:8000/health/ready
```

С клиентского компьютера из `<CLIENT_NETWORK>`:

```bash
curl --fail http://<APP_SERVER_IP>:8000/health/ready
```

Попытка подключения к `<DB_SERVER_IP>:5432` с клиентского компьютера должна
не пройти. С `app-server` подключение к БД должно проходить; результат
health-проверки выше подтверждает его на уровне приложения.

Проверяйте также сетевой firewall провайдера или облака: он должен повторять
те же правила — API-порт доступен только клиентской сети, а `5432` только
`<APP_SERVER_IP>`.
