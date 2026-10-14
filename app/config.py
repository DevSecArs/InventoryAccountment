from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """Настройки приложения из переменных окружения."""

    DATABASE_URL: str = ""
    POSTGRES_HOST: str = "db"
    POSTGRES_USER: str = "inventory_app"
    POSTGRES_PASSWORD: str = "local_inventory_password"
    POSTGRES_DB: str = "inventory"

    @model_validator(mode="after")
    def configure_database(self) -> "Settings":
        if not self.DATABASE_URL:
            self.DATABASE_URL = URL.create(
                "postgresql+psycopg2",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=5432,
                database=self.POSTGRES_DB,
            ).render_as_string(hide_password=False)
        return self

    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_PORT: int = 8000
    APP_HOST: str = "0.0.0.0"

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
