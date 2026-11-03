import hashlib
from typing import Any, Dict, List, Literal, Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Runtime Environment & Dev Sandbox Guardrails
    app_env: Literal["production", "staging", "local_dev", "test"] = "production"
    debug: bool = False
    dev_auth_bypass: bool = False
    dev_user_id: int = 9990001

    # Telegram Bot & Mini App
    bot_token: str
    bot_username: str = "sports_manager_bot"
    webapp_short_name: str = "game"
    admin_ids: List[int] = []
    allowed_users: List[int] = []
    system_owner_id: Optional[int] = None
    webhook_url: str = ""

    # Feature Flags
    debug_new_logic_user_ids: List[int] = []
    use_new_roster_logic: bool = True
    last_legacy_game_id: int = 0

    # PostgreSQL & Connection Pool Sizing
    postgres_user: str = "postgres"
    postgres_password: str = ""
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "football"
    db_pool_size: int = 8
    db_max_overflow: int = 8

    # Redis & Logical Database Isolation
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: Optional[str] = None
    redis_fsm_db: int = 0
    redis_cache_db: int = 1
    redis_stream_db: int = 2

    # Rating & Gamification Defaults
    elo_k_factor_base: int = 25
    elo_k_factor_pro: int = 50
    elo_pro_threshold: int = 10
    elo_win_bonus: int = 10
    elo_loss_penalty: int = 15
    show_rating: bool = False

    # Infrastructure Process Toggles
    use_polling: bool = False
    webapp_url: str = "https://app.example.com"
    webapp_version: str = "3.0.0"
    run_migrations: bool = True
    run_scheduler: bool = True
    run_consumer: bool = True
    run_bot: bool = True

    # Platform Localization, Currency & Onboarding Defaults (ADR-01, ADR-02, ADR-04)
    default_locale: str = "en"
    default_timezone: str = "Europe/Prague"
    default_currency: str = "CZK"
    support_contact: str = ""
    registration_mode: Literal["approval_required", "open_saas"] = "open_saas"

    # Bootstrap Seed Chats
    initial_chats: List[Dict[str, Any]] = []

    @model_validator(mode="after")
    def enforce_sandbox_security_invariants(self) -> "Settings":
        if self.dev_auth_bypass and self.app_env != "local_dev":
            raise ValueError(
                "CRITICAL SECURITY VIOLATION: DEV_AUTH_BYPASS=True is strictly forbidden "
                f"outside APP_ENV='local_dev' (current APP_ENV='{self.app_env}')."
            )
        return self

    @property
    def clean_webapp_url(self) -> str:
        return self.webapp_url.rstrip("/")

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def build_redis_url(self, db: int = 0) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/{db}"
        return f"redis://{self.redis_host}:{self.redis_port}/{db}"

    @property
    def REDIS_URL(self) -> str:
        return self.build_redis_url(self.redis_fsm_db)

    @property
    def REDIS_CACHE_URL(self) -> str:
        return self.build_redis_url(self.redis_cache_db)

    @property
    def REDIS_STREAM_URL(self) -> str:
        return self.build_redis_url(self.redis_stream_db)

    @property
    def webhook_secret_token(self) -> str:
        return hashlib.sha256(self.bot_token.encode()).hexdigest()


settings = Settings()
