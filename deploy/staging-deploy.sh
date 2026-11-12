#!/usr/bin/env bash
set -euo pipefail
umask 077

if [[ "$(id -un)" != "gha-runner" ]]; then
  echo "Развёртывание требует пользователя gha-runner" >&2
  exit 1
fi

if (( $# != 1 && $# != 4 )); then
  echo "Использование: staging-deploy SHA [BACKEND_IMAGE FRONTEND_IMAGE DB_IMAGE]" >&2
  exit 1
fi

registry="192.168.56.111:5000/inventory"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
compose="$script_dir/docker-compose.staging.yml"
state_dir="/opt/actions-runner/staging"
config="$state_dir/staging.env"
images="$state_dir/images.env"
exec 9>"$state_dir/deploy.lock"
echo 'Ожидание блокировки staging'
flock -x 9
echo 'Блокировка staging получена'
release=$1
[[ "$release" =~ ^[0-9a-f]{40}$ ]] || { echo 'Некорректный SHA выпуска' >&2; exit 1; }
record="$state_dir/releases/$release.env"

if (( $# == 1 )); then
  test -f "$record" || { echo 'Успешный выпуск не найден' >&2; exit 1; }
  mapfile -t lines < "$record"
  (( ${#lines[@]} == 3 )) || { echo 'Неполный набор образов' >&2; exit 1; }
  [[ "${lines[0]}" == STAGING_BACKEND_IMAGE=* && "${lines[1]}" == STAGING_FRONTEND_IMAGE=* && "${lines[2]}" == STAGING_DB_IMAGE=* ]] || { echo 'Некорректный набор образов' >&2; exit 1; }
  set -- "$release" "${lines[0]#STAGING_BACKEND_IMAGE=}" "${lines[1]#STAGING_FRONTEND_IMAGE=}" "${lines[2]#STAGING_DB_IMAGE=}"
fi

validate_image() {
  local service="$1" reference="$2" prefix digest
  prefix="${registry}/${service}@sha256:"
  digest="${reference#"$prefix"}"
  if [[ "$reference" != "$prefix"* || ! "$digest" =~ ^[0-9a-f]{64}$ ]]; then
    echo "Недопустимая ссылка на образ: ${service}" >&2
    exit 1
  fi
}

validate_image backend "$2"
validate_image frontend "$3"
validate_image db "$4"

test -f "$compose"
test -f "$config"

for reference in "$2" "$3" "$4"; do
  docker pull "$reference"
done

tmp="$(mktemp "$state_dir/images.env.XXXXXX")"
record_tmp=""
trap 'rm -f "$tmp"; if [[ -n "$record_tmp" ]]; then rm -f "$record_tmp"; fi' EXIT

printf 'STAGING_BACKEND_IMAGE=%s\n' "$2" > "$tmp"
printf 'STAGING_FRONTEND_IMAGE=%s\n' "$3" >> "$tmp"
printf 'STAGING_DB_IMAGE=%s\n' "$4" >> "$tmp"

chmod 600 "$tmp"
mkdir -p "$state_dir/releases"
if [[ -e "$record" ]] && ! cmp -s "$record" "$tmp"; then
  echo 'Выпуск уже записан с другим набором образов' >&2
  exit 1
fi

docker compose \
  --env-file "$config" \
  --env-file "$tmp" \
  -f "$compose" config --quiet

docker compose \
  --env-file "$config" \
  --env-file "$tmp" \
  -f "$compose" \
  up -d --no-build --wait --wait-timeout 180

mapfile -t containers < <(docker ps -aq --filter label=com.docker.compose.project=inventory-staging)
(( ${#containers[@]} == 4 )) || { echo 'Ожидались четыре контейнера staging' >&2; exit 1; }
db_count=0
backend_count=0
nginx_count=0
for container in "${containers[@]}"; do
  read -r service status health < <(docker inspect --format '{{index .Config.Labels "com.docker.compose.service"}} {{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}' "$container")
  [[ "$status" == running && "$health" == healthy ]] || { echo "Контейнер staging не готов: $service" >&2; exit 1; }
  case "$service" in
    db) ((db_count+=1)) ;;
    backend) ((backend_count+=1)) ;;
    nginx) ((nginx_count+=1)) ;;
    *) echo "Неизвестный сервис staging: $service" >&2; exit 1 ;;
  esac
done
(( db_count == 1 && backend_count == 2 && nginx_count == 1 )) || { echo 'Некорректный состав staging' >&2; exit 1; }

curl --fail --silent --show-error \
  --retry 5 --retry-delay 2 \
  http://192.168.56.111:8081/health/ready \
  > /dev/null

mapfile -t replicas < <(docker ps -q --filter label=com.docker.compose.project=inventory-staging --filter label=com.docker.compose.service=backend)
(( ${#replicas[@]} == 2 )) || { echo 'Ожидались две реплики backend' >&2; exit 1; }
for replica in "${replicas[@]}"; do
  docker exec -e EXPECTED_SHA="$release" "$replica" /opt/app-root/src/.venv/bin/python -c 'import json, os, sys, urllib.request; sys.exit(0 if json.load(urllib.request.urlopen("http://127.0.0.1:8000/version", timeout=5))["sha"] == os.environ["EXPECTED_SHA"] else 1)'
done
curl --fail --silent --show-error http://192.168.56.111:8081/version | \
  EXPECTED_SHA="$release" python3 -c 'import json, os, sys; sys.exit(0 if json.load(sys.stdin)["sha"] == os.environ["EXPECTED_SHA"] else 1)'

if [[ ! -e "$record" ]]; then
  record_tmp="$(mktemp "$state_dir/releases/.release.XXXXXX")"
  cp -- "$tmp" "$record_tmp"
  ln -- "$record_tmp" "$record"
  rm -f "$record_tmp"
  record_tmp=""
fi
mv -f "$tmp" "$images"

echo "Staging deployment: OK"
