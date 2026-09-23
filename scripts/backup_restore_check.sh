#!/bin/sh

set -eu

fail() {
    echo "$1" >&2
    exit 2
}

[ "${APP_ENV:-}" = "test" ] || fail "Проверка backup/restore разрешена только при APP_ENV=test"
case "${PGDATABASE:-}" in
    *_test) ;;
    *) fail "Проверка backup/restore требует БД с суффиксом _test" ;;
esac

backup_dir="${1:-/backups}"
target_database="inventory_backup_restore_$(date -u +%Y%m%d%H%M%S)"
backup_file=""

cleanup() {
    dropdb --if-exists "$target_database" >/dev/null 2>&1 || true
    [ -z "$backup_file" ] || rm -f "$backup_file" "${backup_file}.metadata"
    psql --dbname="$PGDATABASE" --quiet --command \
        'TRUNCATE TABLE user_sessions, users, materials, suppliers, units RESTART IDENTITY CASCADE' >/dev/null || true
}
trap cleanup EXIT HUP INT TERM

psql --dbname="$PGDATABASE" --set ON_ERROR_STOP=1 --quiet <<'SQL'
TRUNCATE TABLE user_sessions, users, materials, suppliers, units RESTART IDENTITY CASCADE;
INSERT INTO units (id, code, name) VALUES ('backup-unit', 'KG', 'Килограмм');
INSERT INTO suppliers (id, code, name) VALUES ('backup-supplier', 'BACKUP-SUP', 'Поставщик для проверки');
INSERT INTO materials (id, sku, name, unit_id)
VALUES ('backup-material', 'BACKUP-MAT', 'Материал до повреждения', 'backup-unit');
SQL

source_control="$(psql --dbname="$PGDATABASE" --tuples-only --no-align --command \
    "SELECT m.sku || '|' || m.name || '|' || u.code || '|' || s.code FROM materials m JOIN units u ON u.id = m.unit_id CROSS JOIN suppliers s WHERE m.id = 'backup-material'")"
source_counts="$(psql --dbname="$PGDATABASE" --tuples-only --no-align --command \
    "SELECT (SELECT count(*) FROM units) || '|' || (SELECT count(*) FROM suppliers) || '|' || (SELECT count(*) FROM materials)")"
source_revision="$(psql --dbname="$PGDATABASE" --tuples-only --no-align --command 'SELECT version_num FROM alembic_version')"

backup_output="$(sh /scripts/backup_restore.sh backup "$backup_dir")"
printf '%s\n' "$backup_output"
backup_file="$(printf '%s\n' "$backup_output" | awk -F= '$1 == "BACKUP_PATH" { print $2; exit }')"
[ -n "$backup_file" ] || fail "Команда backup не вернула путь к дампу"

psql --dbname="$PGDATABASE" --set ON_ERROR_STOP=1 --quiet --command \
    "UPDATE materials SET name = 'Материал после повреждения' WHERE id = 'backup-material'"
damaged_control="$(psql --dbname="$PGDATABASE" --tuples-only --no-align --command \
    "SELECT name FROM materials WHERE id = 'backup-material'")"
[ "$damaged_control" = "Материал после повреждения" ] || fail "Не удалось намеренно повредить тестовые данные"

TARGET_DATABASE="$target_database" BACKUP_FILE="$backup_file" sh /scripts/backup_restore.sh restore
restored_control="$(psql --dbname="$target_database" --tuples-only --no-align --command \
    "SELECT m.sku || '|' || m.name || '|' || u.code || '|' || s.code FROM materials m JOIN units u ON u.id = m.unit_id CROSS JOIN suppliers s WHERE m.id = 'backup-material'")"
restored_counts="$(psql --dbname="$target_database" --tuples-only --no-align --command \
    "SELECT (SELECT count(*) FROM units) || '|' || (SELECT count(*) FROM suppliers) || '|' || (SELECT count(*) FROM materials)")"
restored_revision="$(psql --dbname="$target_database" --tuples-only --no-align --command 'SELECT version_num FROM alembic_version')"

[ "$restored_control" = "$source_control" ] || fail "Контрольное значение или связь не восстановлены"
[ "$restored_counts" = "$source_counts" ] || fail "Количество строк после восстановления не совпадает"
[ "$restored_revision" = "$source_revision" ] || fail "Alembic revision после восстановления не совпадает"

echo "CHECK_BACKUP_PATH=$backup_file"
echo "CHECK_BACKUP_SHA256=$(sha256sum "$backup_file" | awk '{print $1}')"
echo "SOURCE_CONTROL=$source_control"
echo "RESTORED_CONTROL=$restored_control"
echo "Проверка backup/restore успешно завершена"
