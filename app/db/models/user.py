from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum, BigInteger, UniqueConstraint, Float, JSON
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base
from app.db.models.enums import Position, Language


class User(Base):
    """
    Database model representing a system user/football player.
    Stores ELO rating, total matches played, MVP count, and player preferences.
    """
    __tablename__ = "users"
    user_id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=False)
    player_position = Column(Enum(Position, name="user_position", native_enum=False), nullable=False)
    stats_matches = Column(Integer, default=0)
    stats_mvp = Column(Integer, default=0)
    rating = Column(Integer, default=100)  # ELO Rating
    games_played = Column(Integer, default=0)
    alt_positions = Column(ARRAY(String), default=[])
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_superadmin = Column(Boolean, default=False)
    is_guest = Column(Boolean, default=False, nullable=False)
    has_multisport_card = Column(Boolean, default=False, nullable=False)
    is_anonymized = Column(Boolean, default=False, nullable=False)
    language = Column(Enum(Language, name="chat_language_enum", native_enum=False), default=Language.en)

    games_created = relationship("Game", back_populates="creator")
    signups = relationship("Signup", back_populates="user")
    votes_cast = relationship("Vote", foreign_keys="[Vote.voter_id]", back_populates="voter")
    votes_received = relationship("Vote", foreign_keys="[Vote.target_id]", back_populates="target")
    profiles = relationship("PlayerProfile", back_populates="user", cascade="all, delete-orphan")
    admin_in_chats = relationship("ChatAdmin", back_populates="user", cascade="all, delete-orphan")
    cards = relationship("PlayerCard", foreign_keys="[PlayerCard.user_id]", back_populates="user", cascade="all, delete-orphan")
    org_memberships = relationship("OrganizationMember", back_populates="user", cascade="all, delete-orphan")



class RatingHistory(Base):
    """
    Database model tracking historical ELO changes of a player per match.
    """
    __tablename__ = "rating_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id"), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False, index=True)
    old_rating = Column(Integer, nullable=False)
    new_rating = Column(Integer, nullable=False)
    change = Column(Integer, nullable=False)
    date = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", backref="rating_history")
    game = relationship("Game", back_populates="rating_history")

    __table_args__ = (
        UniqueConstraint('game_id', 'user_id', name='uq_rating_history_game_user'),
    )



class PlayerCard(Base):
    """
    Database model representing a disciplinary card (Yellow or Red) issued to a player in a specific group.
    Red card blocks registration for matches in that group until expiration.
    Yellow card acts as an official warning.
    """
    __tablename__ = "player_cards"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    chat_id = Column(BigInteger, ForeignKey("chats.chat_id", ondelete="CASCADE"), nullable=False, index=True)
    card_type = Column(String(10), nullable=False)  # "YELLOW" | "RED"
    weeks = Column(Integer, nullable=False, default=4)
    reason = Column(String, nullable=True)
    issued_by = Column(BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    issued_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    user = relationship("User", foreign_keys=[user_id], back_populates="cards")
    issuer = relationship("User", foreign_keys=[issued_by])
    chat = relationship("Chat", back_populates="player_cards")


