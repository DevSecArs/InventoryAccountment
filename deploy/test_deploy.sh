#!/usr/bin/env bash

set -Eeuo pipefail

readonly TEST_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly DEPLOY_SCRIPT="${TEST_DIR}/deploy.sh"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf -- "$TEMP_DIR"' EXIT

bash -n "$DEPLOY_SCRIPT"

set +e
missing_output="$(DEPLOY_ENV_FILE="${TEMP_DIR}/missing.env" bash "$DEPLOY_SCRIPT" 2>&1)"
missing_status=$?
set -e
[[ $missing_status -eq 2 ]]
grep -q 'не найден файл' <<< "$missing_output"

cat > "${TEMP_DIR}/valid.env" <<'EOF'
DEPLOY_ROLE=db
ENABLE_FIREWALL=true
SSH_NETWORK=10.10.1.0/24
APP_SERVER_IP=10.20.0.10
EOF

valid_output="$(DEPLOY_ENV_FILE="${TEMP_DIR}/valid.env" bash "$DEPLOY_SCRIPT" --validate-only)"
grep -q 'корректна для роли db' <<< "$valid_output"

cat > "${TEMP_DIR}/valid-app.env" <<'EOF'
DEPLOY_ROLE=app
REPOSITORY_URL=https://git.invalid/organization/InventoryAccountment.git
REPOSITORY_BRANCH=main
DATABASE_URL=postgresql+psycopg2://inventory:encoded_password@10.20.0.20:5432/inventory
ENABLE_FIREWALL=true
SSH_NETWORK=10.10.1.0/24
CLIENT_NETWORK=10.10.0.0/24
EOF

valid_app_output="$(DEPLOY_ENV_FILE="${TEMP_DIR}/valid-app.env" bash "$DEPLOY_SCRIPT" --validate-only)"
grep -q 'корректна для роли app' <<< "$valid_app_output"

cat > "${TEMP_DIR}/unknown.env" <<'EOF'
DEPLOY_ROLE=db
ENABLE_FIREWALL=true
SSH_NETWORK=10.10.1.0/24
APP_SERVER_IP=10.20.0.10
UNKNOWN_SETTING=value
EOF

set +e
unknown_output="$(DEPLOY_ENV_FILE="${TEMP_DIR}/unknown.env" bash "$DEPLOY_SCRIPT" --validate-only 2>&1)"
unknown_status=$?
set -e
[[ $unknown_status -eq 1 ]]
grep -q 'Неизвестная настройка' <<< "$unknown_output"

printf 'deploy tests: OK\n'
