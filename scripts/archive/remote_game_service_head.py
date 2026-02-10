from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.db.models import Game, Chat, User, Signup, SignupStatus, GameStatus, Team, Vote
from app.api.schemas import GameCreate, GameFinishRequest, GameUpdate
from datetime import datetime, timedelta
import logging

# Scheduler imports (Lazy import inside methods often better to avoid circular, but here ok)
from app.scheduler.main import scheduler
from app.scheduler.tasks import send_voting_message, release_gk_slots, remind_admin_to_finish, publish_game_task
from app.bot.utils import format_game_message
from app.bot.keyboards import get_game_keyboard
from app.db.models import RatingHistory, GameStats


import logging

logger = logging.getLogger(__name__)

class GameActionError(Exception):
    """Base exception for game actions."""
    pass

class GameFullError(GameActionError):
    pass

class AlreadySignedUpError(GameActionError):
    pass

class CancellationLockedError(GameActionError):
