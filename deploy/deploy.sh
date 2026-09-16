#!/usr/bin/env bash

set -Eeuo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly DEPLOY_ENV_FILE="${DEPLOY_ENV_FILE:-${SCRIPT_DIR}/.env}"
readonly DEPLOY_COMMAND="${1:-deploy}"

[[ $# -le 1 ]] || { printf 'Использование: %s [--validate-only]\n' "$0" >&2; exit 2; }
[[ "$DEPLOY_COMMAND" == deploy || "$DEPLOY_COMMAND" == --validate-only ]] || { printf 'Неизвестный аргумент: %s\n' "$DEPLOY_COMMAND" >&2; exit 2; }

log() {
    printf '[deploy] %s\n' "$*"
}

fail() {
    printf '[deploy] ОШИБКА: %s\n' "$*" >&2
    exit 1
}

if [[ ! -f "$DEPLOY_ENV_FILE" ]]; then
    printf 'Рядом со скриптом не найден файл %s\n' "$DEPLOY_ENV_FILE" >&2
    printf 'Создайте его из примера: cp %s/.env.example %s/.env\n' "$SCRIPT_DIR" "$SCRIPT_DIR" >&2
    exit 2
fi

readonly ALLOWED_ENV_KEYS=' DEPLOY_ROLE REPOSITORY_URL REPOSITORY_BRANCH APP_DIR SERVICE_USER SERVICE_GROUP SERVICE_HOME CONFIG_DIR RUNTIME_ENV_FILE APP_SERVICE_NAME MIGRATION_SERVICE_NAME FRONTEND_SERVICE_NAME DATABASE_URL APP_ENV APP_DEBUG BACKEND_HOST BACKEND_PORT FRONTEND_HOST FRONTEND_PORT CLIENT_NETWORK SSH_NETWORK SSH_PORT APP_SERVER_IP DB_PORT ENABLE_FIREWALL EXPOSE_BACKEND RUN_MIGRATIONS NODE_MAJOR NODE_MIN_VERSION PNPM_VERSION '

load_env_file() {
    local line key value line_number=0
    while IFS= read -r line || [[ -n "$line" ]]; do
        line_number=$((line_number + 1))
        line="${line%$'\r'}"
        [[ -z "$line" || "$line" == \#* ]] && continue
        [[ "$line" == *=* ]] || fail "Строка ${line_number} в .env должна иметь формат ИМЯ=ЗНАЧЕНИЕ"

        key="${line%%=*}"
        value="${line#*=}"
        [[ "$key" =~ ^[A-Z][A-Z0-9_]*$ ]] || fail "Недопустимое имя '${key}' в строке ${line_number}"
        [[ "$ALLOWED_ENV_KEYS" == *" ${key} "* ]] || fail "Неизвестная настройка '${key}' в строке ${line_number}"

        if [[ ${#value} -ge 2 && "$value" == \"*\" && "$value" == *\" ]]; then
            value="${value:1:${#value}-2}"
        elif [[ ${#value} -ge 2 && "$value" == \'*\' && "$value" == *\' ]]; then
            value="${value:1:${#value}-2}"
        fi
        [[ "$value" != *$'\n'* ]] || fail "Многострочные значения в .env не поддерживаются"
        printf -v "$key" '%s' "$value"
        export "$key"
    done < "$DEPLOY_ENV_FILE"
}

load_env_file

: "${DEPLOY_ROLE:=app}"
: "${REPOSITORY_BRANCH:=main}"
: "${APP_DIR:=/opt/InventoryAccountment}"
: "${SERVICE_USER:=inv_acc}"
: "${SERVICE_GROUP:=$SERVICE_USER}"
: "${SERVICE_HOME:=/var/lib/InventoryAccountment}"
: "${CONFIG_DIR:=/etc/InventoryAccountment}"
: "${RUNTIME_ENV_FILE:=${CONFIG_DIR}/InventoryAccountment.env}"
: "${APP_SERVICE_NAME:=InventoryAccountment.service}"
: "${MIGRATION_SERVICE_NAME:=InventoryAccountment-migrate.service}"
: "${FRONTEND_SERVICE_NAME:=InventoryAccountment-frontend.service}"
: "${APP_ENV:=production}"
: "${APP_DEBUG:=false}"
: "${BACKEND_HOST:=127.0.0.1}"
: "${BACKEND_PORT:=8000}"
: "${FRONTEND_HOST:=0.0.0.0}"
: "${FRONTEND_PORT:=4173}"
: "${SSH_PORT:=22}"
: "${DB_PORT:=5432}"
: "${ENABLE_FIREWALL:=true}"
: "${EXPOSE_BACKEND:=false}"
: "${RUN_MIGRATIONS:=true}"
: "${NODE_MAJOR:=22}"
: "${NODE_MIN_VERSION:=22.13.0}"
: "${PNPM_VERSION:=11.19.0}"

require_var() {
    local name="$1"
    [[ -n "${!name:-}" ]] || fail "В .env не задана обязательная настройка ${name}"
}

validate_bool() {
    local name="$1" value="${!1:-}"
    [[ "$value" == true || "$value" == false ]] || fail "${name} должно быть true или false"
}

validate_port() {
    local name="$1" value="${!1:-}"
    [[ "$value" =~ ^[0-9]+$ ]] && (( value >= 1 && value <= 65535 )) || fail "${name} содержит недопустимый порт"
}

validate_network() {
    local name="$1" value="${!1:-}"
    [[ "$value" =~ ^[0-9A-Fa-f:.]+(/[0-9]{1,3})?$ ]] || fail "${name} должен содержать IP-адрес или CIDR"
}

validate_common_config() {
    [[ "$DEPLOY_ROLE" == app || "$DEPLOY_ROLE" == db ]] || fail "DEPLOY_ROLE должен быть app или db"
    [[ "$SERVICE_USER" =~ ^[a-z_][a-z0-9_-]*$ ]] || fail "Недопустимое имя SERVICE_USER"
    [[ "$SERVICE_GROUP" =~ ^[a-z_][a-z0-9_-]*$ ]] || fail "Недопустимое имя SERVICE_GROUP"
    [[ "$APP_DIR" == /* && "$APP_DIR" != *[[:space:]]* ]] || fail "APP_DIR должен быть абсолютным путём без пробелов"
    [[ "$SERVICE_HOME" == /* && "$SERVICE_HOME" != *[[:space:]]* ]] || fail "SERVICE_HOME должен быть абсолютным путём без пробелов"
    [[ "$SERVICE_HOME" != "$APP_DIR" && "$SERVICE_HOME" != "$APP_DIR"/* ]] || fail "SERVICE_HOME должен находиться вне APP_DIR"
    [[ "$CONFIG_DIR" == /* && "$CONFIG_DIR" != *[[:space:]]* ]] || fail "CONFIG_DIR должен быть абсолютным путём без пробелов"
    [[ "$RUNTIME_ENV_FILE" == "$CONFIG_DIR"/* && "$RUNTIME_ENV_FILE" != *[[:space:]]* ]] || fail "RUNTIME_ENV_FILE должен находиться внутри CONFIG_DIR"
    validate_bool ENABLE_FIREWALL
    validate_bool EXPOSE_BACKEND
    validate_bool RUN_MIGRATIONS
    validate_port SSH_PORT
    validate_port DB_PORT
    if [[ "$ENABLE_FIREWALL" == true ]]; then
        require_var SSH_NETWORK
        validate_network SSH_NETWORK
    fi
}

validate_app_config() {
    require_var REPOSITORY_URL
    require_var REPOSITORY_BRANCH
    require_var DATABASE_URL
    [[ "$REPOSITORY_URL" != *example.com* ]] || fail "Замените пример REPOSITORY_URL на адрес репозитория"
    [[ "$DATABASE_URL" != *CHANGE_ME* ]] || fail "Замените CHANGE_ME в DATABASE_URL"
    require_var CLIENT_NETWORK
    validate_network CLIENT_NETWORK
    validate_port BACKEND_PORT
    validate_port FRONTEND_PORT
    validate_bool APP_DEBUG
    [[ "$NODE_MAJOR" =~ ^[0-9]+$ ]] || fail "NODE_MAJOR должен быть целым числом"
    [[ "$NODE_MIN_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "NODE_MIN_VERSION должен иметь формат X.Y.Z"
    [[ "$PNPM_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || fail "PNPM_VERSION должен иметь формат X.Y.Z"
    [[ "${NODE_MIN_VERSION%%.*}" == "$NODE_MAJOR" ]] || fail "NODE_MAJOR должен совпадать с major-версией NODE_MIN_VERSION"
    [[ "$APP_SERVICE_NAME" == *.service ]] || fail "APP_SERVICE_NAME должен оканчиваться на .service"
    [[ "$MIGRATION_SERVICE_NAME" == *.service ]] || fail "MIGRATION_SERVICE_NAME должен оканчиваться на .service"
    [[ "$FRONTEND_SERVICE_NAME" == *.service ]] || fail "FRONTEND_SERVICE_NAME должен оканчиваться на .service"
    [[ "$APP_SERVICE_NAME" =~ ^[A-Za-z0-9_.@-]+\.service$ ]] || fail "Недопустимое APP_SERVICE_NAME"
    [[ "$MIGRATION_SERVICE_NAME" =~ ^[A-Za-z0-9_.@-]+\.service$ ]] || fail "Недопустимое MIGRATION_SERVICE_NAME"
    [[ "$FRONTEND_SERVICE_NAME" =~ ^[A-Za-z0-9_.@-]+\.service$ ]] || fail "Недопустимое FRONTEND_SERVICE_NAME"
    [[ "$BACKEND_HOST" =~ ^[A-Za-z0-9_.:-]+$ ]] || fail "Недопустимое значение BACKEND_HOST"
    [[ "$FRONTEND_HOST" =~ ^[A-Za-z0-9_.:-]+$ ]] || fail "Недопустимое значение FRONTEND_HOST"
    [[ "$DATABASE_URL" != *"'"* ]] || fail "Одинарную кавычку в DATABASE_URL нужно percent-encode"
    [[ "$APP_ENV" != *"'"* ]] || fail "Одинарная кавычка в APP_ENV не поддерживается"
}

validate_db_config() {
    if [[ "$ENABLE_FIREWALL" == true ]]; then
        require_var APP_SERVER_IP
        validate_network APP_SERVER_IP
    fi
}

validate_common_config
if [[ "$DEPLOY_ROLE" == app ]]; then
    validate_app_config
else
    validate_db_config
fi

if [[ "$DEPLOY_COMMAND" == --validate-only ]]; then
    log "Конфигурация ${DEPLOY_ENV_FILE} корректна для роли ${DEPLOY_ROLE}"
    exit 0
fi

(( EUID == 0 )) || fail "Запустите скрипт от root: sudo ${SCRIPT_DIR}/deploy.sh"

if [[ "$(stat -c '%a' "$DEPLOY_ENV_FILE")" != 600 ]]; then
    log "Ограничиваю права на ${DEPLOY_ENV_FILE} до 600"
    chmod 600 "$DEPLOY_ENV_FILE"
fi

if [[ ! -r /etc/os-release ]]; then
    fail "Не удалось определить операционную систему"
fi
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == ubuntu ]] || fail "Автоматическая установка поддерживает только Ubuntu"
command -v systemctl >/dev/null || fail "systemd не найден"

APT_UPDATED=false

apt_update_once() {
    if [[ "$APT_UPDATED" == false ]]; then
        log "Обновляю индекс пакетов APT"
        DEBIAN_FRONTEND=noninteractive apt-get update
        APT_UPDATED=true
    fi
}

ensure_packages() {
    local missing=() package
    for package in "$@"; do
        if ! dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed'; then
            missing+=("$package")
        fi
    done
    if (( ${#missing[@]} == 0 )); then
        log "Пакеты уже установлены: $*"
        return
    fi
    apt_update_once
    log "Устанавливаю пакеты: ${missing[*]}"
    DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing[@]}"
}

ensure_base_packages() {
    ensure_packages ca-certificates curl git gnupg ufw
}

ensure_python() {
    if command -v python3.11 >/dev/null && \
       [[ "$(python3.11 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" == 3.11 ]] && \
       python3.11 -c 'import ensurepip, venv' >/dev/null 2>&1; then
        log "Python 3.11 с поддержкой venv уже установлен"
        return
    fi

    apt_update_once
    if ! apt-cache show python3.11 >/dev/null 2>&1 || ! apt-cache show python3.11-venv >/dev/null 2>&1; then
        ensure_packages software-properties-common
        if ! grep -Rqs '^deb .*deadsnakes' /etc/apt/sources.list /etc/apt/sources.list.d 2>/dev/null; then
            log "Добавляю PPA deadsnakes для Python 3.11"
            add-apt-repository -y ppa:deadsnakes/ppa
            APT_UPDATED=false
            apt_update_once
        fi
    fi

    if command -v python3.11 >/dev/null && [[ "$(python3.11 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" == 3.11 ]]; then
        log "Python 3.11 уже установлен"
    else
        ensure_packages python3.11
    fi
    ensure_packages python3.11-venv
    python3.11 --version
}

version_at_least() {
    local actual="$1" required="$2"
    [[ "$(printf '%s\n%s\n' "$required" "$actual" | sort -V | head -n1)" == "$required" ]]
}

ensure_node() {
    local actual='' node_path=''
    if command -v node >/dev/null; then
        actual="$(node -p 'process.versions.node')"
        node_path="$(readlink -f "$(command -v node)")"
    fi
    if [[ -n "$actual" ]] && version_at_least "$actual" "$NODE_MIN_VERSION" && [[ "$node_path" == /usr/bin/* || "$node_path" == /usr/local/bin/* ]]; then
        log "Системный Node.js ${actual} уже соответствует требованию >= ${NODE_MIN_VERSION}"
        return
    fi

    local setup_script
    setup_script="$(mktemp)"
    log "Настраиваю репозиторий NodeSource для Node.js ${NODE_MAJOR}.x"
    curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" -o "$setup_script"
    bash "$setup_script"
    rm -f -- "$setup_script"
    APT_UPDATED=true
    DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs

    actual="$(node -p 'process.versions.node')"
    version_at_least "$actual" "$NODE_MIN_VERSION" || fail "Установлен Node.js ${actual}, требуется >= ${NODE_MIN_VERSION}"
}

ensure_pnpm() {
    local actual=''
    if command -v pnpm >/dev/null; then
        actual="$(pnpm --version)"
    fi
    if [[ "$actual" == "$PNPM_VERSION" ]]; then
        log "pnpm ${PNPM_VERSION} уже установлен"
        return
    fi
    log "Устанавливаю pnpm ${PNPM_VERSION} системно"
    npm install --global "pnpm@${PNPM_VERSION}"
    [[ "$(pnpm --version)" == "$PNPM_VERSION" ]] || fail "Не удалось установить pnpm ${PNPM_VERSION}"
}

ensure_service_account() {
    if ! getent group "$SERVICE_GROUP" >/dev/null; then
        log "Создаю системную группу ${SERVICE_GROUP}"
        groupadd --system "$SERVICE_GROUP"
    else
        log "Группа ${SERVICE_GROUP} уже существует"
    fi

    if ! id "$SERVICE_USER" >/dev/null 2>&1; then
        log "Создаю системного пользователя ${SERVICE_USER}"
        useradd --system --gid "$SERVICE_GROUP" --home-dir "$SERVICE_HOME" --shell /usr/sbin/nologin --no-create-home "$SERVICE_USER"
    else
        log "Пользователь ${SERVICE_USER} уже существует"
    fi
    install -d -m 0750 -o "$SERVICE_USER" -g "$SERVICE_GROUP" "$SERVICE_HOME"
}

ensure_app_ownership() {
    [[ -e "$APP_DIR" ]] || return
    if find "$APP_DIR" \( ! -user "$SERVICE_USER" -o ! -group "$SERVICE_GROUP" \) -print -quit | grep -q .; then
        log "Исправляю владельца файлов в ${APP_DIR}"
        chown -R "$SERVICE_USER:$SERVICE_GROUP" "$APP_DIR"
    else
        log "Владелец файлов ${APP_DIR} уже настроен"
    fi
}

run_as_service() {
    runuser -u "$SERVICE_USER" -- env HOME="$SERVICE_HOME" PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin" "$@"
}

run_in_app_as_service() {
    run_as_service bash -c 'cd -- "$1" && shift && exec "$@"' bash "$APP_DIR" "$@"
}

CODE_CHANGED=false

ensure_repository() {
    if [[ ! -e "$APP_DIR" ]]; then
        install -d -m 0755 -o "$SERVICE_USER" -g "$SERVICE_GROUP" "$APP_DIR"
    fi

    if [[ ! -d "$APP_DIR/.git" ]]; then
        if [[ -n "$(find "$APP_DIR" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
            fail "${APP_DIR} существует, не пуст и не является Git-репозиторием"
        fi
        log "Клонирую ветку ${REPOSITORY_BRANCH}"
        run_as_service git clone --branch "$REPOSITORY_BRANCH" --single-branch "$REPOSITORY_URL" "$APP_DIR"
        CODE_CHANGED=true
        return
    fi

    local current_remote current_commit target_commit current_branch
    current_remote="$(run_as_service git -C "$APP_DIR" remote get-url origin)"
    [[ "$current_remote" == "$REPOSITORY_URL" ]] || fail "origin не совпадает с REPOSITORY_URL; исправьте настройку или remote вручную"
    [[ -z "$(run_as_service git -C "$APP_DIR" status --porcelain)" ]] || fail "В ${APP_DIR} есть локальные изменения; обновление остановлено"

    log "Проверяю обновления origin/${REPOSITORY_BRANCH}"
    run_as_service git -C "$APP_DIR" fetch --prune origin "$REPOSITORY_BRANCH"
    current_branch="$(run_as_service git -C "$APP_DIR" branch --show-current)"
    if [[ "$current_branch" != "$REPOSITORY_BRANCH" ]]; then
        if run_as_service git -C "$APP_DIR" show-ref --verify --quiet "refs/heads/${REPOSITORY_BRANCH}"; then
            run_as_service git -C "$APP_DIR" switch "$REPOSITORY_BRANCH"
        else
            run_as_service git -C "$APP_DIR" switch --track -c "$REPOSITORY_BRANCH" "origin/${REPOSITORY_BRANCH}"
        fi
    fi

    current_commit="$(run_as_service git -C "$APP_DIR" rev-parse HEAD)"
    target_commit="$(run_as_service git -C "$APP_DIR" rev-parse "origin/${REPOSITORY_BRANCH}")"
    if [[ "$current_commit" == "$target_commit" ]]; then
        log "Ветка ${REPOSITORY_BRANCH} уже актуальна (${current_commit:0:12})"
        return
    fi
    if ! run_as_service git -C "$APP_DIR" merge-base --is-ancestor "$current_commit" "$target_commit"; then
        fail "Локальная ветка ${REPOSITORY_BRANCH} содержит собственные или расходящиеся commits; автоматическое обновление остановлено"
    fi
    log "Обновляю ветку ${REPOSITORY_BRANCH} только fast-forward"
    run_as_service git -C "$APP_DIR" merge --ff-only "origin/${REPOSITORY_BRANCH}"
    CODE_CHANGED=true
}

PYTHON_CHANGED=false

ensure_python_environment() {
    local venv_dir="${APP_DIR}/venv"
    local stamp_file="${venv_dir}/.inventory-pyproject.sha256"
    local required_hash
    required_hash="$(sha256sum "${APP_DIR}/pyproject.toml" | awk '{print $1}')"

    if [[ ! -x "${venv_dir}/bin/python" ]]; then
        if [[ -e "$venv_dir" ]]; then
            fail "${venv_dir} существует, но не содержит исполняемый Python; исправьте или удалите его вручную"
        fi
        log "Создаю Python-окружение ${venv_dir}"
        run_as_service python3.11 -m venv "$venv_dir"
        run_as_service "${venv_dir}/bin/python" -m pip install --upgrade pip
        PYTHON_CHANGED=true
    elif [[ "$(run_as_service "${venv_dir}/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')" != 3.11 ]]; then
        fail "Существующее окружение ${venv_dir} создано не на Python 3.11; замените его вручную"
    fi

    if [[ -f "$stamp_file" && "$(<"$stamp_file")" == "$required_hash" ]] && run_as_service "${venv_dir}/bin/python" -c 'import alembic, fastapi, psycopg2, sqlalchemy, uvicorn' >/dev/null 2>&1; then
        log "Python-зависимости уже соответствуют pyproject.toml"
        return
    fi

    log "Устанавливаю Python-зависимости"
    run_as_service "${venv_dir}/bin/python" -m pip install "$APP_DIR"
    printf '%s\n' "$required_hash" > "$stamp_file"
    chown "$SERVICE_USER:$SERVICE_GROUP" "$stamp_file"
    PYTHON_CHANGED=true
}

FRONTEND_CHANGED=false

ensure_frontend() {
    local frontend_dir="${APP_DIR}/frontend"
    local dependency_stamp="${frontend_dir}/node_modules/.inventory-pnpm-lock.sha256"
    local build_stamp="${frontend_dir}/dist/.inventory-commit"
    local lock_hash commit
    lock_hash="$(sha256sum "${frontend_dir}/package.json" "${frontend_dir}/pnpm-lock.yaml" | sha256sum | awk '{print $1}')"
    commit="$(run_as_service git -C "$APP_DIR" rev-parse HEAD)"

    if [[ ! -f "$dependency_stamp" || "$(cat "$dependency_stamp" 2>/dev/null || true)" != "$lock_hash" || ! -f "${frontend_dir}/node_modules/vite/bin/vite.js" ]]; then
        log "Устанавливаю frontend-зависимости"
        run_as_service pnpm --dir "$frontend_dir" install --frozen-lockfile
        printf '%s\n' "$lock_hash" > "$dependency_stamp"
        chown "$SERVICE_USER:$SERVICE_GROUP" "$dependency_stamp"
        FRONTEND_CHANGED=true
    else
        log "Frontend-зависимости уже соответствуют pnpm-lock.yaml"
    fi

    if [[ ! -f "${frontend_dir}/dist/index.html" || ! -f "$build_stamp" || "$(cat "$build_stamp" 2>/dev/null || true)" != "$commit" ]]; then
        log "Собираю frontend"
        run_as_service pnpm --dir "$frontend_dir" run build
        printf '%s\n' "$commit" > "$build_stamp"
        chown "$SERVICE_USER:$SERVICE_GROUP" "$build_stamp"
        FRONTEND_CHANGED=true
    else
        log "Frontend уже собран для commit ${commit:0:12}"
    fi
}

CONFIG_CHANGED=false

ensure_runtime_config() {
    local desired
    desired="$(mktemp)"
    {
        printf "DATABASE_URL='%s'\n" "$DATABASE_URL"
        printf "APP_ENV='%s'\n" "$APP_ENV"
        printf "APP_DEBUG='%s'\n" "$APP_DEBUG"
        printf "APP_HOST='%s'\n" "$BACKEND_HOST"
        printf "APP_PORT='%s'\n" "$BACKEND_PORT"
    } > "$desired"

    install -d -m 0750 -o root -g "$SERVICE_GROUP" "$CONFIG_DIR"
    if [[ -f "$RUNTIME_ENV_FILE" ]] && cmp -s "$desired" "$RUNTIME_ENV_FILE"; then
        log "Runtime-конфигурация уже актуальна"
    else
        log "Обновляю ${RUNTIME_ENV_FILE}"
        install -m 0640 -o root -g "$SERVICE_GROUP" "$desired" "$RUNTIME_ENV_FILE"
        CONFIG_CHANGED=true
    fi
    rm -f -- "$desired"
}

SYSTEMD_CHANGED=false

install_unit_if_changed() {
    local name="$1" source_file="$2" target="/etc/systemd/system/${name}"
    if [[ -f "$target" ]] && cmp -s "$source_file" "$target"; then
        log "Unit ${name} уже актуален"
        return
    fi
    log "Устанавливаю unit ${name}"
    install -m 0644 -o root -g root "$source_file" "$target"
    SYSTEMD_CHANGED=true
}

ensure_systemd_units() {
    local migration_unit app_unit frontend_unit node_bin
    migration_unit="$(mktemp)"
    app_unit="$(mktemp)"
    frontend_unit="$(mktemp)"
    node_bin="$(readlink -f "$(command -v node)")"

    cat > "$migration_unit" <<EOF
[Unit]
Description=InventoryAccountment database migrations
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${RUNTIME_ENV_FILE}
ExecStart=${APP_DIR}/venv/bin/python -m alembic upgrade head
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=full
EOF

    cat > "$app_unit" <<EOF
[Unit]
Description=InventoryAccountment API
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${RUNTIME_ENV_FILE}
ExecStart=${APP_DIR}/venv/bin/python -m uvicorn app.main:app --host ${BACKEND_HOST} --port ${BACKEND_PORT}
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target
EOF

    cat > "$frontend_unit" <<EOF
[Unit]
Description=InventoryAccountment frontend preview
After=network-online.target ${APP_SERVICE_NAME}
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${APP_DIR}/frontend
ExecStart=${node_bin} ${APP_DIR}/frontend/node_modules/vite/bin/vite.js preview --host ${FRONTEND_HOST} --port ${FRONTEND_PORT}
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectHome=true
ProtectSystem=full

[Install]
WantedBy=multi-user.target
EOF

    install_unit_if_changed "$MIGRATION_SERVICE_NAME" "$migration_unit"
    install_unit_if_changed "$APP_SERVICE_NAME" "$app_unit"
    install_unit_if_changed "$FRONTEND_SERVICE_NAME" "$frontend_unit"
    rm -f -- "$migration_unit" "$app_unit" "$frontend_unit"

    if [[ "$SYSTEMD_CHANGED" == true ]]; then
        log "Перечитываю конфигурацию systemd"
        systemctl daemon-reload
    fi
}

ensure_migrations() {
    if [[ "$RUN_MIGRATIONS" == false ]]; then
        log "Миграции отключены настройкой RUN_MIGRATIONS=false"
        return
    fi

    local current
    current="$(run_in_app_as_service env DATABASE_URL="$DATABASE_URL" APP_ENV="$APP_ENV" APP_DEBUG="$APP_DEBUG" "${APP_DIR}/venv/bin/python" -m alembic current 2>&1 || true)"
    if grep -q '(head)' <<< "$current"; then
        log "База данных уже находится на актуальной ревизии Alembic"
        return
    fi
    log "Применяю миграции через ${MIGRATION_SERVICE_NAME}"
    systemctl start "$MIGRATION_SERVICE_NAME"
}

ensure_service_running() {
    local service="$1" restart_required="$2"
    if ! systemctl is-enabled --quiet "$service"; then
        log "Включаю автозапуск ${service}"
        systemctl enable "$service"
    else
        log "Автозапуск ${service} уже включён"
    fi

    if ! systemctl is-active --quiet "$service"; then
        log "Запускаю ${service}"
        systemctl start "$service"
    elif [[ "$restart_required" == true ]]; then
        log "Перезапускаю ${service} после изменений"
        systemctl restart "$service"
    else
        log "Служба ${service} уже запущена и не требует перезапуска"
    fi
}

ufw_rule_exists() {
    local source="$1" port="$2"
    LC_ALL=C ufw status | awk -v expected_port="${port}/tcp" -v expected_source="$source" '
        $1 == expected_port && $2 == "ALLOW" && $3 == expected_source { found = 1 }
        END { exit(found ? 0 : 1) }
    '
}

ensure_ufw_rule() {
    local source="$1" port="$2" comment="$3"
    if ufw_rule_exists "$source" "$port"; then
        log "UFW уже разрешает ${source} → tcp/${port}"
    else
        log "Разрешаю ${source} → tcp/${port} (${comment})"
        ufw allow from "$source" to any port "$port" proto tcp comment "$comment"
    fi
}

assert_no_broader_ufw_rule() {
    local source="$1" port="$2" rule
    while IFS= read -r rule; do
        [[ "$rule" == ufw\ allow* ]] || continue
        if [[ "$rule" == *"port ${port}"* || "$rule" == *"${port}/tcp"* ]]; then
            [[ "$rule" == *"from ${source}"* ]] || fail "Найдено более широкое правило UFW для tcp/${port}: ${rule}. Удалите его вручную и повторите запуск"
        fi
    done < <(LC_ALL=C ufw show added)
}

assert_no_ufw_allow_for_port() {
    local port="$1" rule
    while IFS= read -r rule; do
        [[ "$rule" == ufw\ allow* ]] || continue
        if [[ "$rule" == *"port ${port}"* || "$rule" == *"${port}/tcp"* ]]; then
            fail "Найдено разрешающее правило UFW для закрытого tcp/${port}: ${rule}. Удалите его вручную и повторите запуск"
        fi
    done < <(LC_ALL=C ufw show added)
}

ensure_firewall_defaults() {
    if ! LC_ALL=C ufw status verbose | grep -Fq 'Default: deny (incoming)'; then
        log "Устанавливаю политику UFW: запрещать входящие соединения"
        ufw default deny incoming
    else
        log "Политика UFW для входящих соединений уже deny"
    fi
    if ! LC_ALL=C ufw status verbose | grep -Fq 'allow (outgoing)'; then
        log "Устанавливаю политику UFW: разрешать исходящие соединения"
        ufw default allow outgoing
    else
        log "Политика UFW для исходящих соединений уже allow"
    fi
}

enable_ufw_if_needed() {
    if LC_ALL=C ufw status | grep -Fq 'Status: active'; then
        log "UFW уже включён"
    else
        log "Включаю UFW"
        ufw --force enable
    fi
}

configure_app_firewall() {
    [[ "$ENABLE_FIREWALL" == true ]] || { log "Настройка UFW отключена"; return; }
    assert_no_broader_ufw_rule "$CLIENT_NETWORK" "$FRONTEND_PORT"
    ensure_ufw_rule "$SSH_NETWORK" "$SSH_PORT" 'InventoryAccountment SSH'
    ensure_ufw_rule "$CLIENT_NETWORK" "$FRONTEND_PORT" 'InventoryAccountment frontend'
    if [[ "$EXPOSE_BACKEND" == true ]]; then
        assert_no_broader_ufw_rule "$CLIENT_NETWORK" "$BACKEND_PORT"
        ensure_ufw_rule "$CLIENT_NETWORK" "$BACKEND_PORT" 'InventoryAccountment API'
    else
        assert_no_ufw_allow_for_port "$BACKEND_PORT"
    fi
    ensure_firewall_defaults
    enable_ufw_if_needed
}

configure_db_firewall() {
    [[ "$ENABLE_FIREWALL" == true ]] || { log "Настройка UFW отключена"; return; }
    assert_no_broader_ufw_rule "$APP_SERVER_IP" "$DB_PORT"
    ensure_ufw_rule "$SSH_NETWORK" "$SSH_PORT" 'InventoryAccountment SSH'
    ensure_ufw_rule "$APP_SERVER_IP" "$DB_PORT" 'InventoryAccountment PostgreSQL'
    ensure_firewall_defaults
    enable_ufw_if_needed
    log "Порт PostgreSQL разрешён только для ${APP_SERVER_IP}; также проверьте listen_addresses и pg_hba.conf"
}

verify_application() {
    local attempt
    for attempt in {1..10}; do
        if curl --fail --silent --show-error "http://127.0.0.1:${BACKEND_PORT}/health/live" >/dev/null && \
           curl --fail --silent --show-error "http://127.0.0.1:${BACKEND_PORT}/health/ready" >/dev/null; then
            log "API прошло проверки live и ready"
            break
        fi
        if (( attempt == 10 )); then
            systemctl status "$APP_SERVICE_NAME" --no-pager || true
            fail "API не прошло health-проверки"
        fi
        sleep 2
    done

    curl --fail --silent --show-error "http://127.0.0.1:${FRONTEND_PORT}" >/dev/null || {
        systemctl status "$FRONTEND_SERVICE_NAME" --no-pager || true
        fail "Frontend не отвечает на 127.0.0.1:${FRONTEND_PORT}"
    }
    log "Frontend отвечает на порту ${FRONTEND_PORT}"
}

main_app() {
    ensure_base_packages
    ensure_python
    ensure_node
    ensure_pnpm
    ensure_service_account
    ensure_app_ownership
    ensure_repository
    ensure_python_environment
    ensure_frontend
    ensure_runtime_config
    ensure_systemd_units
    ensure_migrations

    local backend_restart=false frontend_restart=false
    if [[ "$CODE_CHANGED" == true || "$PYTHON_CHANGED" == true || "$CONFIG_CHANGED" == true || "$SYSTEMD_CHANGED" == true ]]; then
        backend_restart=true
    fi
    if [[ "$CODE_CHANGED" == true || "$FRONTEND_CHANGED" == true || "$SYSTEMD_CHANGED" == true ]]; then
        frontend_restart=true
    fi
    ensure_service_running "$APP_SERVICE_NAME" "$backend_restart"
    ensure_service_running "$FRONTEND_SERVICE_NAME" "$frontend_restart"
    configure_app_firewall
    verify_application
    log "Развёртывание приложения завершено"
}

main_db() {
    ensure_packages ufw
    configure_db_firewall
    log "Настройка firewall сервера БД завершена"
}

if [[ "$DEPLOY_ROLE" == app ]]; then
    main_app
else
    main_db
fi
