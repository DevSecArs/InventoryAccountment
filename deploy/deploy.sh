#!/bin/sh
# Развёртывание единственного поддерживаемого Compose-контура.
set -eu
repo_root="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$repo_root"
case "${1:-}" in
    --validate-only) docker compose -f docker-compose.yaml config --quiet ;;
    "") docker compose -f docker-compose.yaml up --build --detach --wait ;;
    *) echo "Использование: deploy/deploy.sh [--validate-only]" >&2; exit 2 ;;
esac
