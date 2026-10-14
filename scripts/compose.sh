#!/bin/sh
# ENV_FILE читается как данные, без source/eval и раскрытия пути в сообщениях.
set -eu
if [ -n "${ENV_FILE:-}" ]; then
    if [ ! -f "$ENV_FILE" ] || [ ! -r "$ENV_FILE" ]; then
        echo 'ENV_FILE должен указывать на доступный для чтения файл.' >&2
        exit 2
    fi
    set -- --env-file "$ENV_FILE" "$@"
fi
exec docker compose "$@"
