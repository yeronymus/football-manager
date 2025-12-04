from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, BigInteger, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.database import Base

class Position(str, enum.Enum):
    GK = "GK"
    DEF = "DEF"
    MID = "MID"
    FWD = "FWD"

class GameStatus(str, enum.Enum):
    OPEN = "open"
    ACTIVE = "active"
    FINISHED = "finished"
    CANCELLED = "cancelled"

class SignupStatus(str, enum.Enum):
    ACTIVE = "active"
    RESERVE = "reserve"
    CANCELLED = "cancelled"

class Team(str, enum.Enum):
    A = "A"
    B = "B"

class User(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=False)
    position = Column(Enum(Position), nullable=False)
    stats_matches = Column(Integer, default=0)
    stats_mvp = Column(Integer, default=0)
    rating = Column(Integer, default=1200)  # ELO Rating
    games_played = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    games_created = relationship("Game", back_populates="creator")
    signups = relationship("Signup", back_populates="user")
    votes_cast = relationship("Vote", foreign_keys="[Vote.voter_id]", back_populates="voter")
    votes_received = relationship("Vote", foreign_keys="[Vote.target_id]", back_populates="target")

class Chat(Base):
    __tablename__ = "chats"

    chat_id = Column(BigInteger, primary_key=True, index=True)
    title = Column(String, nullable=False)

    games = relationship("Game", back_populates="chat")

class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, ForeignKey("chats.chat_id"), nullable=False)
    created_by = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    date_time = Column(DateTime(timezone=True), nullable=False)
    location = Column(String, nullable=False)
    max_players = Column(Integer, default=18)
    status = Column(Enum(GameStatus), default=GameStatus.OPEN)
    winner_team = Column(Enum(Team), nullable=True)
    
    chat = relationship("Chat", back_populates="games")
    creator = relationship("User", back_populates="games_created")
    signups = relationship("Signup", back_populates="game", cascade="all, delete-orphan")
    votes = relationship("Vote", back_populates="game", cascade="all, delete-orphan")

class Signup(Base):
    __tablename__ = "signups"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    status = Column(Enum(SignupStatus), default=SignupStatus.ACTIVE)
    team = Column(Enum(Team), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_paid = Column(Boolean, default=False)

    game = relationship("Game", back_populates="signups")
    user = relationship("User", back_populates="signups")

    __table_args__ = (
        UniqueConstraint('game_id', 'user_id', name='unique_signup'),
    )

class Vote(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    voter_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    target_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)

    game = relationship("Game", back_populates="votes")
    voter = relationship("User", foreign_keys=[voter_id], back_populates="votes_cast")
    target = relationship("User", foreign_keys=[target_id], back_populates="votes_received")

    __table_args__ = (
        UniqueConstraint('game_id', 'voter_id', name='unique_vote'),
    )

class RatingHistory(Base):
    __tablename__ = "rating_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    old_rating = Column(Integer, nullable=False)
    new_rating = Column(Integer, nullable=False)
    change = Column(Integer, nullable=False)
    date = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="rating_history")
    game = relationship("Game", backref="rating_history")
