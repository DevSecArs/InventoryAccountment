#!/usr/bin/env bash
set -euo pipefail
umask 077

if [[ "$(id -un)" != "gha-runner" ]]; then
  echo "Развёртывание требует пользователя gha-runner" >&2
  exit 1
fi

if (( $# != 3 )); then
  echo "Использование: staging-deploy BACKEND_IMAGE FRONTEND_IMAGE DB_IMAGE" >&2
  exit 1
fi

registry="192.168.56.111:5000/inventory"
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
compose="$script_dir/docker-compose.staging.yml"
state_dir="/opt/actions-runner/staging"
config="$state_dir/staging.env"
images="$state_dir/images.env"

validate_image() {
  local service="$1" reference="$2" prefix digest
  prefix="${registry}/${service}@sha256:"
  digest="${reference#"$prefix"}"
  if [[ "$reference" != "$prefix"* || ! "$digest" =~ ^[0-9a-f]{64}$ ]]; then
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

tmp="$(mktemp "$state_dir/images.env.XXXXXX")"
trap 'rm -f "$tmp"' EXIT

printf 'STAGING_BACKEND_IMAGE=%s\n' "$1" > "$tmp"
printf 'STAGING_FRONTEND_IMAGE=%s\n' "$2" >> "$tmp"
printf 'STAGING_DB_IMAGE=%s\n' "$3" >> "$tmp"

chmod 600 "$tmp"

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
  http://192.168.56.111:8081/health/ready \
  > /dev/null

mv -f "$tmp" "$images"

echo "Staging deployment: OK"
