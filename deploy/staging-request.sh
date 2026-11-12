#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -un)" != "gha-runner" ]]; then
  echo "Команда должна выполняться от пользователя gha-runner" >&2
  exit 1
fi

if (( $# != 1 && $# != 4 )); then
  echo "Укажите SHA выпуска и, для автоматического запуска, три digest образов" >&2
  exit 1
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
exec bash "$script_dir/staging-deploy.sh" "$@"
