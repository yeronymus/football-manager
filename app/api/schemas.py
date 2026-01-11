from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.db.models import Team

class GameCreate(BaseModel):
    chat_id: int
    date_time: datetime
    location: str
    max_players: int = 18
    price: int = 100
    payment_info: str = "2924402033/0800"
    team_count: int = 2
    initData: str

class BalanceTeams(BaseModel):
    game_id: int
    initData: str

class GameResult(BaseModel):
    game_id: int
    winner_team: Team
    initData: str

class PlayerStat(BaseModel):
    user_id: int
    goals: int

class GameFinishRequest(BaseModel):
    game_id: int
    score_a: int
    score_b: int
    winner_team: Optional[Team]
    player_stats: list[PlayerStat]
    initData: str

class UpdateTeamsRequest(BaseModel):
    game_id: int
    team_a: list[int]
    team_b: list[int]
    team_c: Optional[list[int]] = None
    initData: str
