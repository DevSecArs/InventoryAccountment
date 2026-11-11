#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -un)" != "deploy" ]]; then
  echo "Команда должна выполняться от пользователя deploy" >&2
  exit 1
fi

if (( $# != 3 )); then
  echo "Требуются три ссылки на опубликованные образы" >&2
  exit 1
fi

exec sudo -n /usr/local/sbin/inventory-staging-deploy "$@"
