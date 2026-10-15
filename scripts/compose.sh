#!/bin/sh
# ENV_FILE читается как данные, без source/eval и раскрытия пути в сообщениях.
set -eu
# UID/GID оператора задают владельца создаваемых отчётов и резервных копий.
export LOCAL_UID="${LOCAL_UID:-$(id -u)}"
export LOCAL_GID="${LOCAL_GID:-$(id -g)}"
python3 scripts/container_check.py --prepare-only
if [ -n "${ENV_FILE:-}" ]; then
    if [ ! -f "$ENV_FILE" ] || [ ! -r "$ENV_FILE" ]; then
        echo 'ENV_FILE должен указывать на доступный для чтения файл.' >&2
        exit 2
    fi
    set -- --env-file "$ENV_FILE" "$@"
fi
exec docker compose "$@"
