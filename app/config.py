import os
import json
import sys
from dotenv import load_dotenv

# Load .env explicitly
load_dotenv(".env")

class Settings:
    def __init__(self):
        # Allow fail-safe loading
        try:
            self.bot_token = os.getenv("BOT_TOKEN", "")
            
            admin_ids_str = os.getenv("ADMIN_IDS", "[]")
            try:
                self.admin_ids = json.loads(admin_ids_str)
                if isinstance(self.admin_ids, list):
                    self.admin_ids = [int(i) for i in self.admin_ids]
                else:
                    self.admin_ids = []
            except (json.JSONDecodeError, ValueError):
                print(f"Warning: Failed to parse or normalize ADMIN_IDS: {admin_ids_str}")
                self.admin_ids = []

            # Feature Flags - Strangler Fig
            debug_ids_str = os.getenv("DEBUG_NEW_LOGIC_USER_IDS", "[]")
            try:
                self.debug_new_logic_user_ids = json.loads(debug_ids_str)
                if isinstance(self.debug_new_logic_user_ids, list):
                    self.debug_new_logic_user_ids = [int(i) for i in self.debug_new_logic_user_ids]
                else:
                    self.debug_new_logic_user_ids = []
            except:
                self.debug_new_logic_user_ids = []

            self.use_new_roster_logic = os.getenv("USE_NEW_ROSTER_LOGIC", "True").lower() == "true"
            self.last_legacy_game_id = int(os.getenv("LAST_LEGACY_GAME_ID", "0"))

            self.webhook_url = os.getenv("WEBHOOK_URL", "")
            
            # Seeding
            self.initial_chats = [
                {"id": -1003437568976, "title": "FM Chat", "admin_chat_id": -1003652516810},
                {"id": -1003652516810, "title": "FM Admin", "admin_chat_id": None},
                {"id": -1003625911268, "title": "FM Channel", "admin_chat_id": None},
            ]

            self.postgres_user = os.getenv("POSTGRES_USER", "postgres")
            self.postgres_password = os.getenv("POSTGRES_PASSWORD", "password")
            self.postgres_db = os.getenv("POSTGRES_DB", "football")
            self.postgres_host = os.getenv("POSTGRES_HOST", "db")
            self.postgres_port = int(os.getenv("POSTGRES_PORT", "5432"))

            self.redis_host = os.getenv("REDIS_HOST", "redis")
            self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
            self.redis_password = os.getenv("REDIS_PASSWORD", None)

            # ELO
            self.elo_k_factor_base = int(os.getenv("ELO_K_FACTOR_BASE", "25"))
            self.elo_k_factor_pro = int(os.getenv("ELO_K_FACTOR_PRO", "50"))
            self.elo_pro_threshold = int(os.getenv("ELO_PRO_THRESHOLD", "10"))
            self.elo_win_bonus = int(os.getenv("ELO_WIN_BONUS", "10"))
            self.elo_loss_penalty = int(os.getenv("ELO_LOSS_PENALTY", "15"))

            self.show_rating = os.getenv("SHOW_RATING", "False").lower() == "true"
            self.use_polling = os.getenv("USE_POLLING", "False").lower() == "true"
            self.debug = os.getenv("DEBUG", "False").lower() == "true"
            self.webapp_url = os.getenv("WEBAPP_URL", "https://your-domain.com")

            owner = os.getenv("SYSTEM_OWNER_ID")
            self.system_owner_id = int(owner) if owner else None
            

        except Exception as e:
            print(f"Config Init Error: {e}", file=sys.stderr)
            # Default empty to prevent crash, check health for error
            pass

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def REDIS_URL(self) -> str:
        if self.redis_password:
            return f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"
        return f"redis://{self.redis_host}:{self.redis_port}/0"

# Singleton
try:
    settings = Settings()
    print("Config loaded via os.getenv")
except Exception as e:
    print(f"FATAL CONFIG ERROR: {e}")
    raise e
