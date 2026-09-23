"""Проверить линейную цепочку Alembic на изолированных тестовых БД."""

from __future__ import annotations

import ast
import os
from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL, Engine, make_url

from alembic import command
from app.config import settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPORARY_DATABASE_PREFIX = "inventory_migration_"
REQUIRED_TABLES = {
    "alembic_version",
    "materials",
    "suppliers",
    "units",
    "user_sessions",
    "users",
}
REQUIRED_UNIQUE_INDEXES = {
    "materials": "ix_materials_sku",
    "suppliers": "ix_suppliers_code",
    "units": "ix_units_code",
    "user_sessions": "ix_user_sessions_token_hash",
    "users": "ix_users_login",
}
REQUIRED_FOREIGN_KEYS = {
    "materials": ("unit_id", "units", "id", None),
    "user_sessions": ("user_id", "users", "id", "CASCADE"),
}


def _assert_test_environment() -> URL:
    """Не допустить создания или удаления БД вне тестового контура."""
    if os.environ.get("APP_ENV") != "test":
        raise RuntimeError("Проверка миграций разрешена только при APP_ENV=test")

    database_url = make_url(settings.DATABASE_URL)
    if not database_url.database or not database_url.database.endswith("_test"):
        raise RuntimeError("Исходная БД проверки миграций должна оканчиваться на _test")
    return database_url


def _alembic_config(database_url: URL) -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", database_url.render_as_string(hide_password=False))
    return config


def _script_directory() -> ScriptDirectory:
    return ScriptDirectory.from_config(_alembic_config(_assert_test_environment()))


def _assert_nonempty_revisions(script: ScriptDirectory) -> None:
    """Отклонить пустые миграции, которые не меняют схему."""
    for revision in script.walk_revisions():
        tree = ast.parse(Path(revision.path).read_text(encoding="utf-8"))
        upgrade = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.FunctionDef) and node.name == "upgrade"
            ),
            None,
        )
        meaningful_statements = []
        if upgrade:
            meaningful_statements = [
                statement
                for statement in upgrade.body
                if not isinstance(statement, ast.Pass)
                and not (
                    isinstance(statement, ast.Expr)
                    and isinstance(statement.value, ast.Constant)
                    and isinstance(statement.value.value, str)
                )
            ]
        if not meaningful_statements:
            raise RuntimeError(f"Обнаружена пустая миграция: {revision.revision}")


def _single_head_and_previous_revision(script: ScriptDirectory) -> tuple[str, str]:
    heads = script.get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"Ожидается ровно один Alembic head, получено: {len(heads)}")

    head_revision = script.get_revision(heads[0])
    previous_revision = head_revision.down_revision
    if not isinstance(previous_revision, str):
        raise TypeError("Последняя миграция не имеет единственной предыдущей ревизии")
    return heads[0], previous_revision


def _temporary_database_url(base_url: URL, label: str) -> URL:
    database_name = f"{TEMPORARY_DATABASE_PREFIX}{label}_{uuid4().hex[:12]}"
    return base_url.set(database=database_name)


def _assert_temporary_database_name(database_name: str | None) -> str:
    if not database_name or not database_name.startswith(TEMPORARY_DATABASE_PREFIX):
        raise RuntimeError("Разрешено удалять только БД проверки миграций")
    return database_name


def _create_database(base_url: URL, database_url: URL) -> None:
    database_name = _assert_temporary_database_name(database_url.database)
    administration_engine = create_engine(base_url.set(database="postgres"))
    try:
        with administration_engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    finally:
        administration_engine.dispose()


def _drop_database(base_url: URL, database_url: URL) -> None:
    database_name = _assert_temporary_database_name(database_url.database)
    administration_engine = create_engine(base_url.set(database="postgres"))
    try:
        with administration_engine.connect().execution_options(
            isolation_level="AUTOCOMMIT"
        ) as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
    finally:
        administration_engine.dispose()


def _revision_in_database(engine: Engine) -> str:
    with engine.connect() as connection:
        return str(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one())


def _assert_schema(database_url: URL, expected_head: str) -> None:
    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        missing_tables = REQUIRED_TABLES - set(inspector.get_table_names())
        if missing_tables:
            raise RuntimeError(f"В схеме отсутствуют таблицы: {sorted(missing_tables)}")

        for table_name, index_name in REQUIRED_UNIQUE_INDEXES.items():
            index = next(
                (item for item in inspector.get_indexes(table_name) if item["name"] == index_name),
                None,
            )
            if index is None or not index.get("unique"):
                raise RuntimeError(f"Нет уникального индекса {index_name} в таблице {table_name}")

        for table_name, expected_foreign_key in REQUIRED_FOREIGN_KEYS.items():
            column, referred_table, referred_column, ondelete = expected_foreign_key
            foreign_keys = inspector.get_foreign_keys(table_name)
            if not any(
                foreign_key["constrained_columns"] == [column]
                and foreign_key["referred_table"] == referred_table
                and foreign_key["referred_columns"] == [referred_column]
                and foreign_key.get("options", {}).get("ondelete") == ondelete
                for foreign_key in foreign_keys
            ):
                raise RuntimeError(f"Нет внешнего ключа {table_name}.{column}")

        for table_name in REQUIRED_TABLES - {"alembic_version"}:
            if inspector.get_check_constraints(table_name):
                raise RuntimeError(f"Непредусмотренные check constraints в таблице {table_name}")

        if _revision_in_database(engine) != expected_head:
            raise RuntimeError("Версия схемы не совпадает с Alembic head")
    finally:
        engine.dispose()


def _insert_catalog_data(database_url: URL) -> None:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO units (id, code, name) VALUES ('unit-1', 'KG', 'Килограмм')")
            )
            connection.execute(
                text(
                    "INSERT INTO suppliers (id, code, name) VALUES ('supplier-1', 'SUP-1', 'Поставщик')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO materials (id, sku, name, unit_id) "
                    "VALUES ('material-1', 'MAT-1', 'Материал', 'unit-1')"
                )
            )
    finally:
        engine.dispose()


def _assert_catalog_data_preserved(database_url: URL) -> None:
    engine = create_engine(database_url)
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT material.sku, unit.code, supplier.code "
                    "FROM materials AS material "
                    "JOIN units AS unit ON unit.id = material.unit_id "
                    "CROSS JOIN suppliers AS supplier"
                )
            ).all()
        if rows != [("MAT-1", "KG", "SUP-1")]:
            raise RuntimeError("Данные справочников не сохранились после обновления")
    finally:
        engine.dispose()


def _assert_authentication_tables_work(database_url: URL) -> None:
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id, login, password_hash, full_name, role) "
                    "VALUES ('user-1', 'migration-user', 'hash', 'Пользователь миграции', 'operator')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO user_sessions "
                    "(id, user_id, token_hash, csrf_token, expires_at) "
                    "VALUES ('session-1', 'user-1', 'token', 'csrf', CURRENT_TIMESTAMP)"
                )
            )
            session_owner = connection.execute(
                text("SELECT user_id FROM user_sessions WHERE id = 'session-1'")
            ).scalar_one()
        if session_owner != "user-1":
            raise RuntimeError("Новая таблица user_sessions не работает после обновления")
    finally:
        engine.dispose()


def _upgrade(database_url: URL, revision: str) -> None:
    command.upgrade(_alembic_config(database_url), revision)


def _downgrade(database_url: URL, revision: str) -> None:
    command.downgrade(_alembic_config(database_url), revision)


def _check_model_schema_match(database_url: URL) -> None:
    command.check(_alembic_config(database_url))


def _check_clean_database(base_url: URL, head: str, previous_revision: str) -> None:
    database_url = _temporary_database_url(base_url, "clean")
    _create_database(base_url, database_url)
    try:
        _upgrade(database_url, "head")
        _assert_schema(database_url, head)
        _check_model_schema_match(database_url)
        _downgrade(database_url, "-1")
        engine = create_engine(database_url)
        try:
            actual_revision = _revision_in_database(engine)
        finally:
            engine.dispose()
        if actual_revision != previous_revision:
            raise RuntimeError("downgrade -1 не вернул предыдущую ревизию")
        _upgrade(database_url, "head")
        _assert_schema(database_url, head)
    finally:
        _drop_database(base_url, database_url)


def _check_populated_database(base_url: URL, head: str, previous_revision: str) -> None:
    database_url = _temporary_database_url(base_url, "populated")
    _create_database(base_url, database_url)
    try:
        _upgrade(database_url, previous_revision)
        _insert_catalog_data(database_url)
        _upgrade(database_url, "head")
        _assert_schema(database_url, head)
        _assert_catalog_data_preserved(database_url)
        _assert_authentication_tables_work(database_url)
        _check_model_schema_match(database_url)
    finally:
        _drop_database(base_url, database_url)


def main() -> None:
    base_url = _assert_test_environment()
    script = _script_directory()
    _assert_nonempty_revisions(script)
    head, previous_revision = _single_head_and_previous_revision(script)
    _check_clean_database(base_url, head, previous_revision)
    _check_populated_database(base_url, head, previous_revision)
    print("Проверка последовательности миграций успешно завершена")


if __name__ == "__main__":
    main()
