from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum, BigInteger, UniqueConstraint, Float, JSON
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class AdBanner(Base):
    """
    Database model representing advertisement / sponsor banners shown to users.
    Supports rich visuals, click/impression metrics, and non-proprietary MVP rewards.
    """
    __tablename__ = "ad_banners"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(BigInteger, nullable=True)     # ID of the user who owns this ad
    image_url = Column(String, nullable=True)
    hero_image_url = Column(String, nullable=True)
    title = Column(String(128), nullable=True)
    subtitle = Column(String(255), nullable=True)
    badge_text = Column(String(64), nullable=True)
    cta_text = Column(String(64), nullable=True)
    text = Column(String, nullable=False)
    link = Column(String, nullable=True)
    reward_title = Column(String(255), nullable=True)
    reward_instructions = Column(Text, nullable=True)
    impressions_count = Column(Integer, default=0, nullable=False)
    clicks_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True)
    show_probability = Column(Integer, default=100)  # Weight for random selection
    chat_id = Column(BigInteger, ForeignKey("chats.chat_id"), nullable=True) # If null, show everywhere


class AdBannerEvent(Base):
    """
    Granular telemetry for sponsor banner impressions and clicks across Mini App placements.
    """
    __tablename__ = "ad_banner_events"

    id = Column(Integer, primary_key=True, index=True)
    banner_id = Column(Integer, ForeignKey("ad_banners.id", ondelete="CASCADE"), nullable=False, index=True)
    chat_id = Column(BigInteger, nullable=True, index=True)
    user_id = Column(BigInteger, nullable=True, index=True)
    placement = Column(String(64), nullable=True)
    event_type = Column(String(16), nullable=False, index=True)  # "impression" | "click"
    created_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)


class MvpRewardClaim(Base):
    """
    Non-proprietary MVP sponsor reward voucher / claim record.
    Supports both Apple Wallet / loyalty card crediting (via phone/card ID) and direct counter QR redemption.
    """
    __tablename__ = "mvp_reward_claims"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(32), unique=True, nullable=False, index=True)
    chat_id = Column(BigInteger, ForeignKey("chats.chat_id", ondelete="CASCADE"), nullable=False, index=True)
    game_id = Column(Integer, ForeignKey("games.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    banner_id = Column(Integer, ForeignKey("ad_banners.id", ondelete="SET NULL"), nullable=True)
    sponsor_name = Column(String(128), nullable=False)
    reward_title = Column(String(255), nullable=False)
    sponsor_url = Column(String(512), nullable=True)
    loyalty_identifier = Column(String(128), nullable=True)
    status = Column(String(24), default="ISSUED", nullable=False)  # ISSUED | PENDING_CREDIT | CREDITED | REDEEMED
    issued_at = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    redeemed_at = Column(DateTime(timezone=True), nullable=True)

