# Развёртывание InventoryAccountment на Ubuntu Server

Инструкция предназначена для Ubuntu Server 24.04 LTS. Она сначала запускает
все обязательные проверки в изолированном Docker-контуре и только после их
успешного завершения запускает рабочие контейнеры приложения и PostgreSQL.
Текущий Compose-контур публикует FastAPI и PostgreSQL; frontend проходит
проверки, но отдельный production-сервис для его публикации пока не настроен.

Для проверки понадобится сервер минимум с 2 ядрами CPU, 4 ГБ оперативной
памяти и 20 ГБ свободного места. Нужны пользователь с `sudo`, SSH-доступ и
доступ в интернет к GitHub, Docker Hub, PyPI и npm.

## 1. Обновить Ubuntu

**Действие**

Обновите список пакетов и установите базовые утилиты.

**Готовый код**

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y \
  ca-certificates \
  curl \
  git \
  make \
  openssl \
  python3 \
  python3-pip \
  python-is-python3
```

**Краткое описание**

Git получает исходный код, Make запускает команды проекта, Python нужен для
настройки окружения, а OpenSSL — для создания пароля PostgreSQL.

## 2. Установить Docker и Docker Compose

**Действие**

Подключите официальный репозиторий Docker и установите Docker Engine с Compose.

**Готовый код**

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt update
sudo apt install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

**Краткое описание**

После добавления пользователя в группу `docker` завершите SSH-сессию и
подключитесь к серверу снова. Это позволит запускать проект без `sudo`.

## 3. Установить Node.js и pnpm

**Действие**

Установите Node.js 24 и закреплённую проектом версию pnpm.

**Готовый код**

```bash
curl -fsSL https://deb.nodesource.com/setup_24.x -o /tmp/nodesource_setup.sh
sudo -E bash /tmp/nodesource_setup.sh
rm /tmp/nodesource_setup.sh

sudo apt install -y nodejs
sudo npm install --global pnpm@11.19.0
```

**Краткое описание**

Node.js и pnpm нужны для установки, проверки и тестирования frontend. Версия
pnpm совпадает с `frontend/package.json`.

## 4. Проверить установленные инструменты

**Действие**

Убедитесь, что все команды доступны после повторного SSH-подключения.

**Готовый код**

```bash
git --version
make --version
python --version
node --version
pnpm --version
docker --version
docker compose version
docker run --rm hello-world
```

**Краткое описание**

Все команды должны завершиться без ошибок. Если Docker сообщает об отсутствии
прав, повторно войдите на сервер и ещё раз выполните `docker run`.

## 5. Получить исходный код

**Действие**

Клонируйте репозиторий в `/opt` и перейдите на проверяемую ревизию. Для
реального выпуска замените `main` на заранее одобренный тег или commit SHA.

**Готовый код**

```bash
sudo mkdir -p /opt/inventory-accountment
sudo chown "$USER":"$USER" /opt/inventory-accountment

git clone https://github.com/DevSecArs/InventoryAccountment.git \
  /opt/inventory-accountment
cd /opt/inventory-accountment

git fetch --tags --prune origin
git checkout main
git pull --ff-only origin main
git status --short --branch
```

**Краткое описание**

Перед продолжением рабочее дерево должно быть чистым. Для выпуска лучше
использовать точный проверенный commit SHA, чтобы код на сервере нельзя было
незаметно заменить другим состоянием ветки.

## 6. Подготовить изолированное проверочное окружение

**Действие**

Добавьте каталог пользовательских программ в `PATH` и выполните первоначальную
настройку локального проверочного контура.

**Готовый код**

```bash
cd /opt/inventory-accountment
export PATH="$HOME/.local/bin:$PATH"

make setup LOCAL=1 LOCAL_RUN_ID=ubuntu-verify
```

**Краткое описание**

Команда использует безопасный `.env.example`, установит закреплённые Python- и
frontend-зависимости и не будет обращаться к рабочей БД. Значение
`LOCAL_RUN_ID` нужно использовать без изменений во всех проверочных командах.

## 7. Запустить все обязательные тесты

**Действие**

Запустите единый проверочный контур и дождитесь его полного завершения.

**Готовый код**

```bash
cd /opt/inventory-accountment
export PATH="$HOME/.local/bin:$PATH"

make verify \
  LOCAL=1 \
  LOCAL_RUN_ID=ubuntu-verify \
  BASE_REF=origin/main
```

**Краткое описание**

`make verify LOCAL=1` последовательно проверяет:

- lock-файлы и воспроизводимость зависимостей;
- форматирование, Ruff, mypy и Bandit;
- Python- и frontend-зависимости;
- отсутствие секретов через gitleaks;
- backend- и frontend-тесты;
- покрытие backend не ниже 80%;
- критические мутации бизнес-правил;
- миграции на чистой и заполненной PostgreSQL;
- backup, повреждение тестовых данных и restore;
- сборку и Trivy-скан контейнерного образа;
- readiness и HTTP-сценарий API → PostgreSQL;
- очистку временных контейнеров и томов;
- whitespace рабочей копии и разницы с основной веткой.

Развёртывание можно продолжать только при коде завершения `0`. После ошибки
исправьте её причину и повторите всю команду. Не отключайте проверки и не
снижайте пороги.

## 8. Проверить отчёты тестов

**Действие**

Убедитесь, что обязательные отчёты созданы.

**Готовый код**

```bash
cd /opt/inventory-accountment

test -f reports/junit.xml
test -f reports/coverage.xml
test -f reports/bandit.json
test -f reports/pip-audit.json
test -f reports/pnpm-audit.json
test -f reports/gitleaks.json
test -f reports/trivy-image.json

echo "Все обязательные отчёты найдены"
```

**Краткое описание**

Отчёты подтверждают выполнение тестов, покрытия и проверок безопасности.
Каталог `reports/` не следует добавлять в Git.

## 9. Создать рабочую конфигурацию

**Действие**

Создайте системный файл конфигурации с параметрами внешней PostgreSQL и
закройте доступ к нему другим пользователям сервера.

**Готовый код**

```bash
cd /opt/inventory-accountment
sudo install -d -m 750 /etc/InventoryAccountment
sudoedit /etc/InventoryAccountment/InventoryAccountment.env
sudo chown root:inv_acc /etc/InventoryAccountment/InventoryAccountment.env
sudo chmod 640 /etc/InventoryAccountment/InventoryAccountment.env
```

Укажите в открытом редакторе:

```ini
DATABASE_URL=postgresql+psycopg2://<USER>:<PASSWORD>@<DB_HOST>:5432/inventory
APP_ENV=production
APP_DEBUG=false
APP_HOST=127.0.0.1
APP_PORT=8000
```

**Краткое описание**

Рабочая конфигурация отделена от `.env.example`, который используется только
тестами. Файл `/etc/InventoryAccountment/InventoryAccountment.env` содержит
секреты и не входит в Git.

## 10. Применить миграции и запустить приложение

**Действие**

Примените миграции к внешней PostgreSQL и запустите приложение.

**Готовый код**

```bash
cd /opt/inventory-accountment
export PATH="$HOME/.local/bin:$PATH"

make migrate
make run
```

**Краткое описание**

`make migrate` применяет все миграции Alembic к рабочей БД, а `make run`
запускает FastAPI с конфигурацией из системного файла. Схему нельзя создавать
вручную.

## 11. Проверить запущенное приложение

**Действие**

Проверьте оба health-маршрута.

**Готовый код**

```bash
curl --fail --show-error http://127.0.0.1:8000/health/live
curl --fail --show-error http://127.0.0.1:8000/health/ready
```

**Краткое описание**

Оба запроса должны вернуть JSON со статусом `ok`. Проверка `ready` подтверждает
доступность PostgreSQL.

## 12. Подключиться к API с рабочего компьютера

**Действие**

Создайте SSH-туннель с рабочего компьютера. Замените значения пользователя и
адреса сервера на свои.

**Готовый код**

```bash
ssh -L 8000:127.0.0.1:8000 ubuntu@SERVER_IP
```

В другом терминале рабочего компьютера:

```bash
curl http://127.0.0.1:8000/health/ready
```

**Краткое описание**

Туннель предоставляет доступ к API без публикации порта в интернет. После его
создания документация FastAPI доступна на `http://127.0.0.1:8000/docs`.

## 13. Создать первую резервную копию

**Действие**

После успешного запуска создайте проверяемый дамп БД.

**Готовый код**

```bash
cd /opt/inventory-accountment
make backup
ls -lh backups/
```

**Краткое описание**

Команда создаёт дамп и метаданные с контрольной суммой и Alembic revision.
Скопируйте резервную копию в защищённое хранилище вне этого сервера. Не
добавляйте содержимое `backups/` в Git.

## 14. Остановить или повторно запустить проект

**Действие**

Используйте Make-команды для штатной остановки и повторного запуска.

**Готовый код**

```bash
cd /opt/inventory-accountment

make down
make up
make migrate
```

**Краткое описание**

Обычный `make down` не удаляет рабочий том PostgreSQL. Не используйте
`docker compose down --volumes` для рабочего окружения. После перезагрузки
сервера снова выполните `make up` и `make migrate`, если автозапуск отдельно не
настроен.

## 15. Обновить уже развёрнутый проект

**Действие**

Перед обновлением создайте backup, получите новый код, снова выполните весь
локальный контур и только затем обновите рабочие контейнеры.

**Готовый код**

```bash
cd /opt/inventory-accountment
export PATH="$HOME/.local/bin:$PATH"

make backup
git status --short
git fetch --tags --prune origin
git checkout main
git pull --ff-only origin main

make setup LOCAL=1 LOCAL_RUN_ID=ubuntu-upgrade
make verify \
  LOCAL=1 \
  LOCAL_RUN_ID=ubuntu-upgrade \
  BASE_REF=origin/main

make up
make migrate

curl --fail --show-error http://127.0.0.1:8000/health/ready
```

**Краткое описание**

Обновление запрещено продолжать при локальных Git-изменениях или неуспешном
`make verify`. Автоматический откат схемы не выполняется: перед обновлением
нужно определить совместимость предыдущего образа с новой схемой.

## Результат

Развёртывание завершено, когда одновременно выполнены условия:

- `make verify LOCAL=1` завершился с кодом `0`;
- все обязательные отчёты созданы;
- миграции применены без ошибок;
- контейнеры приложения и PostgreSQL имеют состояние `healthy`;
- `/health/live` и `/health/ready` возвращают `ok`;
- первая резервная копия создана и вынесена за пределы сервера.

Локальный успешный запуск не заменяет успешный CI актуального commit SHA,
независимое одобрение, проверку критических файлов и живую приёмку.
