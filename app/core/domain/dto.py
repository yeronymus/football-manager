"""
core/domain/dto.py — Domain Data Transfer Objects.

These dataclasses represent the *business* inputs and outputs for core services.
They have NO dependency on FastAPI, Pydantic, or any transport layer.

The API layer (routers) is responsible for mapping its Pydantic schemas to these DTOs
before calling services.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.db.models import Team


@dataclass
class CreateGameDTO:
    chat_id: int
    date_time: datetime
    location: str
    max_players: int = 18
    price: int = 100
    payment_info: str = "2924402033/0800"
    team_count: int = 2
    gk_hours: int = 48
    duration: float = 2.0
    registration_hours: int = 0
    game_type: str = "regular"
    auto_join_ids: list[int] = field(default_factory=list)
    publish_at: Optional[datetime] = None
    main_players_count: Optional[int] = 22
    signup_limit: Optional[int] = 999


@dataclass
class UpdateGameDTO:
    game_id: int
    location: Optional[str] = None
    date_time: Optional[datetime] = None
    max_players: Optional[int] = None
    price: Optional[int] = None
    payment_info: Optional[str] = None
    gk_hours: Optional[int] = None
    duration: Optional[float] = None
    registration_hours: Optional[int] = None
    main_players_count: Optional[int] = None
    signup_limit: Optional[int] = None


@dataclass
class PlayerStatDTO:
    user_id: int
    goals: int


@dataclass
class FinishGameDTO:
    game_id: int
    score_a: int
    score_b: int
    winner_team: Optional[Team] = None
    mvp_user_id: Optional[int] = None
    mvp_team_a: Optional[int] = None
    mvp_team_b: Optional[int] = None
    player_stats: list[PlayerStatDTO] = field(default_factory=list)
