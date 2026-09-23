#!/bin/sh

set -eu

fail() {
    echo "$1" >&2
    exit 2
}

safe_database_name() {
    case "$1" in
        '' | *[!A-Za-z0-9_]* | [0-9]*) return 1 ;;
        *) return 0 ;;
    esac
}

metadata_value() {
    key="$1"
    file="$2"
    awk -F= -v expected_key="$key" '$1 == expected_key { print substr($0, length(expected_key) + 2); exit }' "$file"
}

database_exists() {
    psql --dbname=postgres --tuples-only --no-align \
        --command "SELECT 1 FROM pg_database WHERE datname = '$1'" | grep -qx '1'
}

postgres_major() {
    pg_dump --version | sed -n 's/.* \([0-9][0-9]*\)\..*/\1/p'
}

create_backup() {
    backup_dir="$1"
    safe_database_name "$PGDATABASE" || fail "Имя исходной БД содержит недопустимые символы"
    mkdir -p "$backup_dir"
    timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
    dump_file="$backup_dir/${PGDATABASE}_${timestamp}.dump"
    metadata_file="${dump_file}.metadata"
    revision="$(psql --tuples-only --no-align --command 'SELECT version_num FROM alembic_version')"

    [ -n "$revision" ] || fail "Не удалось определить Alembic revision"
    pg_dump --format=custom --file="$dump_file" --dbname="$PGDATABASE"
    pg_restore --list "$dump_file" >/dev/null

    checksum="$(sha256sum "$dump_file" | awk '{print $1}')"
    size_bytes="$(wc -c < "$dump_file" | tr -d ' ')"
    major="$(postgres_major)"
    cat > "$metadata_file" <<EOF
created_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
source_database=$PGDATABASE
alembic_revision=$revision
size_bytes=$size_bytes
sha256=$checksum
postgres_major=$major
EOF

    echo "BACKUP_PATH=$dump_file"
    echo "BACKUP_CREATED_AT_UTC=$(metadata_value created_at_utc "$metadata_file")"
    echo "BACKUP_SHA256=$checksum"
    echo "BACKUP_ALEMBIC_REVISION=$revision"
}

restore_backup() {
    backup_file="${BACKUP_FILE:?Не задан BACKUP_FILE}"
    metadata_file="${backup_file}.metadata"
    [ -f "$backup_file" ] || fail "Дамп не найден"
    [ -r "$backup_file" ] || fail "Дамп недоступен для чтения"
    [ -f "$metadata_file" ] || fail "Не найдены метаданные дампа"

    expected_checksum="$(metadata_value sha256 "$metadata_file")"
    expected_size="$(metadata_value size_bytes "$metadata_file")"
    expected_major="$(metadata_value postgres_major "$metadata_file")"
    expected_revision="$(metadata_value alembic_revision "$metadata_file")"
    source_database="$(metadata_value source_database "$metadata_file")"
    [ -n "$expected_checksum" ] && [ -n "$expected_size" ] && [ -n "$expected_major" ] && [ -n "$expected_revision" ] || fail "Метаданные дампа неполные"
    safe_database_name "$source_database" || fail "Метаданные содержат недопустимое имя исходной БД"
    actual_checksum="$(sha256sum "$backup_file" | awk '{print $1}')"
    actual_size="$(wc -c < "$backup_file" | tr -d ' ')"
    [ "$actual_checksum" = "$expected_checksum" ] || fail "Контрольная сумма дампа не совпадает"
    [ "$actual_size" = "$expected_size" ] || fail "Размер дампа не совпадает с метаданными"
    [ "$(postgres_major)" = "$expected_major" ] || fail "Основная версия pg_restore не совместима с дампом"
    pg_restore --list "$backup_file" >/dev/null

    target_database="${TARGET_DATABASE:-${source_database}_restored_$(date -u +%Y%m%d%H%M%S)}"
    safe_database_name "$target_database" || fail "Целевая БД содержит недопустимые символы"
    [ "$target_database" != "$source_database" ] || fail "Нельзя восстановить дамп поверх исходной БД по умолчанию"

    created_target=0
    cleanup_failed_restore() {
        if [ "$created_target" = "1" ]; then
            dropdb --if-exists "$target_database" >/dev/null 2>&1 || true
        fi
    }
    trap cleanup_failed_restore EXIT HUP INT TERM

    if database_exists "$target_database"; then
        [ "${RESTORE_EXISTING:-0}" = "1" ] || fail "Целевая БД существует; укажите RESTORE_EXISTING=1 для явной замены"
        [ -n "${TARGET_DATABASE_URL:-}" ] || fail "Для замены существующей БД требуется TARGET_DATABASE_URL"
        [ "${CONFIRM_TARGET_DATABASE:-}" = "$target_database" ] || fail "Подтверждение имени целевой БД не совпадает"
        case "$TARGET_DATABASE_URL" in
            */"$target_database" | */"$target_database"\?*) ;;
            *) fail "TARGET_DATABASE_URL не указывает на подтверждённую целевую БД" ;;
        esac
        psql --dbname=postgres --command "DROP DATABASE \"$target_database\" WITH (FORCE)"
    fi

    createdb --template=template0 "$target_database"
    created_target=1
    pg_restore --exit-on-error --no-owner --no-privileges --dbname="$target_database" "$backup_file"
    restored_revision="$(psql --dbname="$target_database" --tuples-only --no-align --command 'SELECT version_num FROM alembic_version')"
    [ "$restored_revision" = "$expected_revision" ] || fail "Alembic revision восстановленной БД не совпадает с метаданными"
    trap - EXIT HUP INT TERM

    echo "RESTORED_DATABASE=$target_database"
    echo "RESTORED_ALEMBIC_REVISION=$restored_revision"
}

case "${1:-}" in
    backup) create_backup "${2:-/backups}" ;;
    restore) restore_backup ;;
    *) fail "Использование: backup_restore.sh backup <каталог> | restore" ;;
esac
