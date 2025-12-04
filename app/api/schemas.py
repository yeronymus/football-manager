from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.db.models import Team

class GameCreate(BaseModel):
    chat_id: int
    date_time: datetime
    location: str
    max_players: int = 15
    initData: str

class BalanceTeams(BaseModel):
    game_id: int
    initData: str

class GameResult(BaseModel):
    game_id: int
    winner_team: Team
    initData: str
