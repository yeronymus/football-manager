from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum, BigInteger, UniqueConstraint, Float, JSON
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
from app.db.models.enums import Language


class Chat(Base):
    """
    Database model representing a Telegram group or channel chat.
    Stores group-specific settings for SaaS tenancy, default limits, and pricing.
    """
    __tablename__ = "chats"

    chat_id = Column(BigInteger, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String, nullable=False)
    channel_id = Column(BigInteger, nullable=True)    # Linked Announcement Channel

    # SaaS / Group Settings
    language = Column(Enum(Language, name="chat_language_enum", native_enum=False), default=Language.en)
    payment_info = Column(String, nullable=True)     # If null, uses global default
    is_active = Column(Boolean, default=True)
    currency = Column(String(8), default="CZK")
    timezone = Column(String(64), default="Europe/Prague")
    sport_type = Column(String(32), default="football")
    billing_mode = Column(String(32), default="manual")
    policy = Column(JSON, default=dict)

    # Defaults for Game Creation
    default_location = Column(String, nullable=True)
    default_price = Column(Integer, default=100)
    default_team_count = Column(Integer, default=2)
    default_max_players = Column(Integer, default=26)
    default_main_players_count = Column(Integer, default=22)
    default_duration = Column(Float, default=2.0)
    default_gk_hours = Column(Integer, default=0)
    default_registration_hours = Column(Integer, default=0)
    default_signup_limit = Column(Integer, default=0)

    organization = relationship("Organization", back_populates="chats")
    games = relationship("Game", back_populates="chat")
    players = relationship("PlayerProfile", back_populates="chat", cascade="all, delete-orphan")
    admins = relationship("ChatAdmin", back_populates="chat", cascade="all, delete-orphan")
    members = relationship("ChatMember", back_populates="chat", cascade="all, delete-orphan")
    player_cards = relationship("PlayerCard", back_populates="chat", cascade="all, delete-orphan")
    inventory_items = relationship("InventoryItem", back_populates="chat", cascade="all, delete-orphan")

class PlayerProfile(Base):
    """
    Database model representing a player's statistics specific to a single chat group.
    Used to support different stats/ratings for different leagues/chats.
    """
    __tablename__ = "player_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    chat_id = Column(BigInteger, ForeignKey("chats.chat_id"), nullable=False, index=True)
    
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
    """
    Database model representing admin privileges of a user within a specific group chat.
    """
    __tablename__ = "chat_admins"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, ForeignKey("chats.chat_id"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    
    can_edit_settings = Column(Boolean, default=True)
    can_manage_games = Column(Boolean, default=True)

    chat = relationship("Chat", back_populates="admins")
    user = relationship("User", back_populates="admin_in_chats")

    __table_args__ = (
        UniqueConstraint('chat_id', 'user_id', name='unique_chat_admin'),
    )


class ChatMember(Base):
    """
    Tracks all Telegram group participants observed by the bot (both registered and unregistered).
    Enables tracking of group membership status (member, left, kicked) and outreach to unregistered users.
    """
    __tablename__ = "chat_members"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, ForeignKey("chats.chat_id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    status = Column(String(32), default="member", nullable=False)
    is_registered = Column(Boolean, default=False, nullable=False)
    admin_note = Column(Text, nullable=True)
    loyalty_card_id = Column(String(128), nullable=True)
    first_seen_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now(), nullable=False)

    chat = relationship("Chat", back_populates="members")

    __table_args__ = (
        UniqueConstraint("chat_id", "user_id", name="uq_chat_members_chat_user"),
    )

