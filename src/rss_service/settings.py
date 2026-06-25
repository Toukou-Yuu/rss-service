from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = Field(default="development", alias="RSS_SERVICE_ENV")
    host: str = Field(default="127.0.0.1", alias="RSS_SERVICE_HOST")
    port: int = Field(default=8787, alias="RSS_SERVICE_PORT")
    api_token: str = Field(default="change-me", alias="RSS_SERVICE_API_TOKEN")

    db_path: Path = Field(default=Path("data/rss.sqlite3"), alias="RSS_DB_PATH")
    reports_dir: Path = Field(default=Path("reports"), alias="RSS_REPORTS_DIR")
    config_dir: Path = Field(default=Path("config"), alias="RSS_CONFIG_DIR")
    timezone: str = Field(default="Asia/Singapore", alias="RSS_TIMEZONE")

    user_agent: str = Field(default="rss-service/1.0 (+local-hermes)", alias="RSS_USER_AGENT")
    fetch_concurrency: int = Field(default=8, alias="RSS_FETCH_CONCURRENCY")
    fetch_timeout_seconds: float = Field(default=20.0, alias="RSS_FETCH_TIMEOUT_SECONDS")
    fetch_retry_times: int = Field(default=2, alias="RSS_FETCH_RETRY_TIMES")
    per_domain_concurrency: int = Field(default=2, alias="RSS_PER_DOMAIN_CONCURRENCY")
    summary_max_length: int = Field(default=240, alias="RSS_SUMMARY_MAX_LENGTH")

    enable_internal_scheduler: bool = Field(default=False, alias="RSS_ENABLE_INTERNAL_SCHEDULER")
    log_level: str = Field(default="INFO", alias="RSS_LOG_LEVEL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
