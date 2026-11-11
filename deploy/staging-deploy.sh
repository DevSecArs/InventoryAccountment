#!/usr/bin/env bash
set -euo pipefail
umask 077

if (( EUID != 0 )); then
  echo "Развёртывание требует root" >&2
  exit 1
fi

if (( $# != 3 )); then
  echo "Использование: staging-deploy BACKEND_IMAGE FRONTEND_IMAGE DB_IMAGE" >&2
  exit 1
fi

registry="192.168.56.111:5000/inventory"
compose="/opt/inventory-staging/docker-compose.yml"
config="/etc/inventory-staging/staging.env"
images="/etc/inventory-staging/images.env"

validate_image() {
  local service="$1" reference="$2"
  local pattern="^${registry}/${service}@sha256:[0-9a-f]{64}$"
  if [[ ! "$reference" =~ $pattern ]]; then
    echo "Недопустимая ссылка на образ: ${service}" >&2
    exit 1
  fi
}

validate_image backend "$1"
validate_image frontend "$2"
validate_image db "$3"

test -f "$compose"
test -f "$config"

for reference in "$1" "$2" "$3"; do
  docker pull "$reference"
done

tmp="$(mktemp /etc/inventory-staging/images.env.XXXXXX)"
trap 'rm -f "$tmp"' EXIT

printf 'STAGING_BACKEND_IMAGE=%s\n' "$1" > "$tmp"
printf 'STAGING_FRONTEND_IMAGE=%s\n' "$2" >> "$tmp"
printf 'STAGING_DB_IMAGE=%s\n' "$3" >> "$tmp"

chown root:deploy "$tmp"
chmod 640 "$tmp"

docker compose \
  --env-file "$config" \
  --env-file "$tmp" \
  -f "$compose" config --quiet

docker compose \
  --env-file "$config" \
  --env-file "$tmp" \
  -f "$compose" \
  up -d --no-build --wait --wait-timeout 180

curl --fail --silent --show-error \
  --retry 5 --retry-delay 2 \
  http://127.0.0.1:8081/health/ready \
  > /dev/null

mv -f "$tmp" "$images"

echo "Staging deployment: OK"
