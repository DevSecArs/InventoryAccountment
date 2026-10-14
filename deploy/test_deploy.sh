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
export PATH="$tmp:$PATH" DEPLOY_TEST_LOG="$tmp/command"
sh "$root/deploy/deploy.sh" --validate-only
grep -qx 'compose -f docker-compose.yaml config --quiet' "$DEPLOY_TEST_LOG"
sh "$root/deploy/deploy.sh"
grep -qx 'compose -f docker-compose.yaml up --build --detach --wait' "$DEPLOY_TEST_LOG"
if sh "$root/deploy/deploy.sh" --unsupported; then exit 1; fi
echo 'Compose deploy wrapper: OK'
