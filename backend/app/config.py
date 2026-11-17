"""Application settings — all values come from environment variables (or .env)."""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "development"
    # Main platform database (users, content, progress). Never exposed to user SQL.
    database_url: str = Field(..., description="postgresql+psycopg://user:pass@host:port/db")

    # Sandbox cluster — a *separate* PostgreSQL server.
    sandbox_host: str = "localhost"
    sandbox_port: int = 5434
    sandbox_admin_user: str = "postgres"
    sandbox_admin_password: str = Field(..., description="superuser of the sandbox cluster (provisioning only)")
    sandbox_reader_password: str = Field(..., description="password of the read-only role sbx_reader")
    sandbox_role_secret: str = Field(..., description="HMAC secret used to derive per-user sandbox role passwords")

    # Execution limits
    query_timeout_ms: int = 5000
    max_result_rows: int = 1000
    max_result_sets: int = 10
    max_sql_length: int = 20000
    max_statements: int = 50
    writable_db_max_bytes: int = 200 * 1024 * 1024

    # Auth / sessions
    session_cookie_name: str = "sqlab_session"
    session_ttl_days: int = 14
    cookie_secure: bool = False

    # Rate limits (requests per minute)
    rate_execute_per_min: int = 60
    rate_auth_per_min: int = 10

    timezone: str = "Asia/Bangkok"

    # SQLite engine: exported sample DBs + per-user writable copies (must be a writable directory)
    sqlite_dir: str = "var/sqlite"

    # SQL Learning Assistant (AI layer is optional; provider keys are read from the environment only)
    rate_assistant_per_min: int = 30
    rate_assistant_ai_per_min: int = 6
    assistant_ai_daily_limit: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
