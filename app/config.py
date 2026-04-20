from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List, Dict, Any

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        extra="ignore"
    )

    # Telegram Bot
    bot_token: str
    admin_ids: List[int] = []
    system_owner_id: Optional[int] = None
    webhook_url: str = ""

    # Feature Flags & Debug
    debug_new_logic_user_ids: List[int] = []
    use_new_roster_logic: bool = True
    last_legacy_game_id: int = 0
    debug: bool = False

    # PostgreSQL
    postgres_user: str = "postgres"
    postgres_password: str = "password"
    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "football"

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: Optional[str] = None

    # ELO & Gamification
    elo_k_factor_base: int = 25
    elo_k_factor_pro: int = 50
    elo_pro_threshold: int = 10
    elo_win_bonus: int = 10
    elo_loss_penalty: int = 15
    show_rating: bool = False

    # Infrastructure Options
    use_polling: bool = False
    webapp_url: str = "https://your-domain.com"
    
    # Internal Configuration Seeding (Parsed directly from `.env` string like INITIAL_CHATS='[{"id": -100}]')
    initial_chats: List[Dict[str, Any]] = []

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def REDIS_URL(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"
        return f"redis://{self.redis_host}:{self.redis_port}/0"

# Instantiating the Singleton config. 
# This will Fail-Fast (raise ValidationError) if critical items like `BOT_TOKEN` are omitted in `.env`
settings = Settings()
