from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, Enum, BigInteger, UniqueConstraint, Float, JSON
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class AuditLog(Base):
    """
    Immutable administrative audit ledger recording tenant-scoped mutations (ADR-09).
    Tracks who performed an administrative action, in which tenant chat, on which target entity,
    and with what structured payload.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, ForeignKey("chats.chat_id", ondelete="SET NULL"), nullable=True, index=True)
    actor_user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(64), nullable=False, index=True)
    target_type = Column(String(64), nullable=True)
    target_id = Column(String(64), nullable=True)
    payload = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)


class Organization(Base):
    """
    Top-level B2B SaaS tenant representing a Company, University, or Multi-Branch Club.
    Aggregates multiple Telegram group chats (sports sections, trips, book clubs, quizzes)
    under unified billing, quotas, white-labeling (BYOB), and HR analytics.
    """
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    logo_url = Column(String, nullable=True)
    brand_color = Column(String(16), nullable=True)
    plan_tier = Column(String(32), default="free", nullable=False)  # "free" | "pro" | "enterprise"
    allowed_email_domains = Column(JSON, default=list, nullable=False)
    custom_bot_token_encrypted = Column(String, nullable=True)
    owner_user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    chats = relationship("Chat", back_populates="organization")
    members = relationship("OrganizationMember", back_populates="organization", cascade="all, delete-orphan")


class OrganizationMember(Base):
    """
    Enterprise RBAC membership and employee verification record within an Organization.
    Roles: 'owner' | 'branch_admin' | 'coordinator' | 'auditor' | 'member'.
    """
    __tablename__ = "organization_members"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(32), default="member", nullable=False)
    work_email = Column(String(255), nullable=True)
    is_verified_employee = Column(Boolean, default=False, nullable=False)
    has_multisport_card = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="members")
    user = relationship("User", back_populates="org_memberships")

    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_members_org_user"),
    )


class ShadowIdentityVault(Base):
    """
    Two-tier cold archival identity vault for GDPR Right-to-Erasure compliance.
    Preserves an encrypted snapshot of a user's historical identity before anonymizing
    their public profile to 'Former Participant #ID', ensuring zero loss of historical
    match/event integrity while allowing profile restoration if the user returns.
    """
    __tablename__ = "shadow_identity_vault"

    id = Column(Integer, primary_key=True, index=True)
    original_user_id = Column(BigInteger, nullable=False, index=True)
    organization_id = Column(Integer, nullable=True, index=True)
    chat_id = Column(BigInteger, nullable=True, index=True)
    encrypted_payload = Column(String, nullable=False)
    anonymized_alias = Column(String(128), nullable=False)
    archived_reason = Column(String(64), default="gdpr_erasure", nullable=False)
    archived_by_user_id = Column(BigInteger, nullable=True)
    archived_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


