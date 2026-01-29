from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from app.db.models import Team

class GameCreate(BaseModel):
    chat_id: int
    date_time: datetime
    location: str
    max_players: int = 18
    price: int = 100
    payment_info: str = "2924402033/0800"
    team_count: int = 2
    gk_hours: int = 48
    auto_join_ids: List[int] = []
    publish_at: Optional[datetime] = None
    initData: str

class GameUpdate(BaseModel):
    game_id: int
    location: Optional[str] = None
    date_time: Optional[datetime] = None
    max_players: Optional[int] = None
    price: Optional[int] = None
    payment_info: Optional[str] = None
    gk_hours: Optional[int] = None
    initData: str
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
    score_a: int
    score_b: int
    winner_team: Optional[Team]
    mvp_user_id: Optional[int] = None
    player_stats: list[PlayerStat]
    initData: str

class UpdateTeamsRequest(BaseModel):
    game_id: int
    team_a: list[int]
    team_b: list[int]
    team_c: Optional[list[int]] = None
    initData: str

class AddPlayerRequest(BaseModel):
    game_id: int
    user_id: int
    initData: str

class AddGuestRequest(BaseModel):
    game_id: int
    name: str
    position: str
    initData: str
