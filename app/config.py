"""App settings, read from the .env file in the project root."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

BASE_DIR = Path(__file__).resolve().parent.parent  # .../ecowaste
UPLOAD_DIR = BASE_DIR / "uploads"  # user-uploaded files (photos); not committed, not public


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8-sig", extra="ignore")

    app_name: str = "EcoWaste"
    secret_key: str = "change-me"  # signs the login cookie; set a long random value in .env

    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "ecowaste_db"
    db_user: str = "ecowaste_app"
    db_password: str = ""

    # Optional full override, e.g. "sqlite:///test.db" for quick tests.
    database_url: str | None = None

    @property
    def sqlalchemy_url(self) -> URL | str:
        if self.database_url:
            return self.database_url
        # URL.create escapes special characters in the password for us.
        return URL.create(
            "mysql+pymysql",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            query={"charset": "utf8mb4"},
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
