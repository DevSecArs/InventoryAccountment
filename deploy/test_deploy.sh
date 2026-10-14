#!/bin/sh
# Проверка передачи аргументов Compose без изменения системы.
set -eu
root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
cat > "$tmp/docker" <<'MOCK'
#!/bin/sh
printf '%s\n' "$*" > "$DEPLOY_TEST_LOG"
MOCK
chmod +x "$tmp/docker"
unset ENV_FILE
export PATH="$tmp:$PATH" DEPLOY_TEST_LOG="$tmp/command"
sh "$root/deploy/deploy.sh" --validate-only
grep -qx 'compose -f docker-compose.yaml config --quiet' "$DEPLOY_TEST_LOG"
sh "$root/deploy/deploy.sh"
grep -qx 'compose -f docker-compose.yaml up --build --detach --wait' "$DEPLOY_TEST_LOG"
if sh "$root/deploy/deploy.sh" --unsupported; then exit 1; fi
# Аргументы пишутся построчно: путь с пробелами должен остаться одним аргументом.
cat > "$tmp/docker" <<'MOCK'
#!/bin/sh
printf '%s\n' "$@" > "$DEPLOY_TEST_LOG"
MOCK
mkdir "$tmp/settings directory"
export ENV_FILE="$tmp/settings directory/config.env"
: > "$ENV_FILE"
sh "$root/deploy/deploy.sh" --validate-only
printf '%s\n' compose --env-file "$ENV_FILE" -f docker-compose.yaml config --quiet > "$tmp/expected"
cmp "$tmp/expected" "$DEPLOY_TEST_LOG"
sh "$root/deploy/deploy.sh"
printf '%s\n' compose --env-file "$ENV_FILE" -f docker-compose.yaml up --build --detach --wait > "$tmp/expected"
cmp "$tmp/expected" "$DEPLOY_TEST_LOG"
rm "$DEPLOY_TEST_LOG"
export ENV_FILE="$tmp/missing.env"
if sh "$root/deploy/deploy.sh" --validate-only; then exit 1; fi
test ! -e "$DEPLOY_TEST_LOG"
echo 'Compose deploy wrapper: OK'
