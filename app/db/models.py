from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, BigInteger, UniqueConstraint, Float
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from app.db.database import Base

class Position(str, enum.Enum):
    GK = "GK"
    
    # Defenders
    DEF = "DEF" # General Defender
    LB = "LB"
    CB = "CB"
    RB = "RB"
    LWB = "LWB"
    RWB = "RWB"
    
    # Midfielders
    MID = "MID" # General Midfielder
    CDM = "CDM"
    CM = "CM"
    CAM = "CAM"
    LM = "LM"
    RM = "RM"
    
    # Forwards
    FWD = "FWD" # General Forward
    ST = "ST"
    LW = "LW"
    RW = "RW"
    CF = "CF"
    SUB = "SUB" # Substitute

class GameStatus(str, enum.Enum):
    OPEN = "open"
    ACTIVE = "active"
    FINISHED = "finished"
    CANCELLED = "cancelled"

class GameType(str, enum.Enum):
    REGULAR = "regular"   # Общая игра
    DRAFT = "draft"       # Драфт

class SignupStatus(str, enum.Enum):
    ACTIVE = "active"
    RESERVE = "reserve"
    CANCELLED = "cancelled"

class Team(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"

class User(Base):
    __tablename__ = "users"

    user_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=False)
    player_position = Column(Enum(Position, name="user_position"), nullable=False)
    stats_matches = Column(Integer, default=0)
    stats_mvp = Column(Integer, default=0)
    rating = Column(Integer, default=100)  # ELO Rating
    games_played = Column(Integer, default=0)
    alt_positions = Column(ARRAY(String), default=[])
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_superadmin = Column(Boolean, default=False)

    games_created = relationship("Game", back_populates="creator")
    signups = relationship("Signup", back_populates="user")
    votes_cast = relationship("Vote", foreign_keys="[Vote.voter_id]", back_populates="voter")
    votes_received = relationship("Vote", foreign_keys="[Vote.target_id]", back_populates="target")
    profiles = relationship("PlayerProfile", back_populates="user", cascade="all, delete-orphan")
    admin_in_chats = relationship("ChatAdmin", back_populates="user", cascade="all, delete-orphan")

class Chat(Base):
    __tablename__ = "chats"

    chat_id = Column(BigInteger, primary_key=True, index=True)
    title = Column(String, nullable=False)
    channel_id = Column(BigInteger, nullable=True)    # Linked Announcement Channel

    # SaaS / Group Settings
    language = Column(String, default="ru")
    payment_info = Column(String, nullable=True)     # If null, uses global default
    is_active = Column(Boolean, default=True)

    games = relationship("Game", back_populates="chat")
    players = relationship("PlayerProfile", back_populates="chat", cascade="all, delete-orphan")
    admins = relationship("ChatAdmin", back_populates="chat", cascade="all, delete-orphan")

class PlayerProfile(Base):
    __tablename__ = "player_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    chat_id = Column(BigInteger, ForeignKey("chats.chat_id"), nullable=False)
    
    rating = Column(Integer, default=100)
    games_played = Column(Integer, default=0)
    stats_matches = Column(Integer, default=0)
    stats_mvp = Column(Integer, default=0)

    user = relationship("User", back_populates="profiles")
    chat = relationship("Chat", back_populates="players")

    __table_args__ = (
        UniqueConstraint('user_id', 'chat_id', name='unique_group_profile'),
    )

class ChatAdmin(Base):
    __tablename__ = "chat_admins"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, ForeignKey("chats.chat_id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    
    can_edit_settings = Column(Boolean, default=True)
    can_manage_games = Column(Boolean, default=True)

    chat = relationship("Chat", back_populates="admins")
    user = relationship("User", back_populates="admin_in_chats")

    __table_args__ = (
        UniqueConstraint('chat_id', 'user_id', name='unique_chat_admin'),
    )

class AdBanner(Base):
    __tablename__ = "ad_banners"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(BigInteger, nullable=True)     # ID of the user who owns this ad
    image_url = Column(String, nullable=True)
    text = Column(String, nullable=False)
    link = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    show_probability = Column(Integer, default=100)  # Weight for random selection
    chat_id = Column(BigInteger, ForeignKey("chats.chat_id"), nullable=True) # If null, show everywhere

class Game(Base):
    __tablename__ = "games"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, ForeignKey("chats.chat_id"), nullable=False)
    created_by = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    date_time = Column(DateTime(timezone=True), nullable=False)
    location = Column(String, nullable=False)
    max_players = Column(Integer, default=18)
    price = Column(Integer, default=100)
    payment_info = Column(String, default="2924402033/0800")
    team_count = Column(Integer, default=2)
    gk_hours = Column(Integer, default=48)
    duration = Column(Float, default=2.0) # Match duration in hours
    status = Column(Enum(GameStatus), default=GameStatus.OPEN)
    game_type = Column(Enum(GameType, name="game_type_enum"), default=GameType.REGULAR)
    winner_team = Column(Enum(Team), nullable=True)
    score_a = Column(Integer, nullable=True)
    score_b = Column(Integer, nullable=True)
    score_c = Column(Integer, nullable=True)
    message_id = Column(BigInteger, nullable=True) # Public Group Message
    channel_id = Column(BigInteger, nullable=True) # Channel Chat ID
    channel_message_id = Column(BigInteger, nullable=True) # Channel Message ID
    admin_message_id = Column(BigInteger, nullable=True) # Dashboard Message
    has_active_gk_a = Column(Boolean, default=True)
    has_active_gk_b = Column(Boolean, default=True)
    has_active_gk_c = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # Registration Window (0 = Unlimited, 24 = 24 hours from creation)
    registration_hours = Column(Integer, default=0)
    
    # New Format Fields
    main_players_count = Column(Integer, default=22) # Number of players in "Main Roster"
    signup_limit = Column(Integer, default=999)      # Total players allowed (Active + Reserve)
    
    chat = relationship("Chat", back_populates="games")
    creator = relationship("User", back_populates="games_created")
    signups = relationship("Signup", back_populates="game", cascade="all, delete-orphan")
    votes = relationship("Vote", back_populates="game", cascade="all, delete-orphan")
    rating_history = relationship("RatingHistory", back_populates="game", cascade="all, delete-orphan")
    stats = relationship("GameStats", back_populates="game", cascade="all, delete-orphan")

class Signup(Base):
    __tablename__ = "signups"

    id = Column(Integer, primary_key=True, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False)
    status = Column(Enum(SignupStatus), default=SignupStatus.ACTIVE)
    team = Column(Enum(Team), nullable=True)
    position = Column(Enum(Position, name="signup_position_enum"), nullable=True) # Per-match override
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
    vote_team = Column(Enum(Team, name="vote_team_enum"), nullable=False)

    game = relationship("Game", back_populates="votes")
    voter = relationship("User", foreign_keys=[voter_id], back_populates="votes_cast")
    target = relationship("User", foreign_keys=[target_id], back_populates="votes_received")

    __table_args__ = (
        UniqueConstraint('game_id', 'voter_id', 'vote_team', name='unique_vote_team'),
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
    game = relationship("Game", back_populates="rating_history")

class GameStats(Base):
    __tablename__ = "game_stats"
    
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey("games.id"))
    user_id = Column(BigInteger, ForeignKey("users.user_id"))
    
    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    is_mvp = Column(Boolean, default=False)
    
    game = relationship("Game", back_populates="stats")
    user = relationship("User", backref="match_stats")
