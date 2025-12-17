from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_IDS: List[int]
    WEBHOOK_URL: str
    
    # Seeding
    INITIAL_CHATS: List[dict] = [
        {"id": -1001234567890, "title": "Test Chat"},
        {"id": -1009876543210, "title": "Main Chat"}
    ]
    
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    REDIS_HOST: str
    REDIS_PORT: int

    # ELO Settings
    ELO_K_FACTOR_BASE: int = 25
    ELO_K_FACTOR_PRO: int = 50
    ELO_PRO_THRESHOLD: int = 5 # Games played
    ELO_WIN_BONUS: int = 10
    ELO_LOSS_PENALTY: int = 20
    
    # NEW: Видимость рейтинга
    SHOW_RATING: bool = False
    
    # Local Development
    USE_POLLING: bool = False
    DEBUG: bool = False
    WEBAPP_URL: str = "https://your-domain.com"
    
    # Access Control
    SYSTEM_OWNER_ID: int = None

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    class Config:
        env_file = ".env"

settings = Settings()
