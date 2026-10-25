"""Настройки подключения к PostgreSQL."""

from sqlalchemy.engine import make_url

from app.config import Settings


def test_database_password_is_encoded_without_changing_credentials() -> None:
    password = "local:p@ss/word%?"
    settings = Settings(
        DATABASE_URL="",
        POSTGRES_HOST="db",
        POSTGRES_USER="inventory_app",
        POSTGRES_PASSWORD=password,
        POSTGRES_DB="inventory",
    )
    url = make_url(settings.DATABASE_URL)
    assert url.host == "db"
    assert url.port == 5432
    assert url.password == password
    assert url.database == "inventory"
