from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "finanzas-aftt-api"
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "finanzas_aftt"

    session_secret_key: str = Field(min_length=16)
    session_expire_days: int = 7

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
