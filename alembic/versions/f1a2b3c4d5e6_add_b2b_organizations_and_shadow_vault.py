"""Add B2B organizations, RBAC memberships, user MultiSport/anonymization flags, and ShadowIdentityVault

Revision ID: f1a2b3c4d5e6
Revises: e7f8a9b0c1d2
Create Date: 2026-11-10 16:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e7f8a9b0c1d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "organizations" not in existing_tables:
        op.create_table(
            "organizations",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("slug", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("logo_url", sa.String(), nullable=True),
            sa.Column("brand_color", sa.String(length=16), nullable=True),
            sa.Column("plan_tier", sa.String(length=32), server_default="free", nullable=False),
            sa.Column("allowed_email_domains", sa.JSON(), nullable=False),
            sa.Column("custom_bot_token_encrypted", sa.String(), nullable=True),
            sa.Column(
                "owner_user_id",
                sa.BigInteger(),
                sa.ForeignKey("users.user_id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint("slug", name="uq_organizations_slug"),
        )
        op.create_index("ix_organizations_id", "organizations", ["id"])
        op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)
        op.create_index("ix_organizations_owner_user_id", "organizations", ["owner_user_id"])

    if "organization_members" not in existing_tables:
        op.create_table(
            "organization_members",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column(
                "organization_id",
                sa.Integer(),
                sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.BigInteger(),
                sa.ForeignKey("users.user_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("role", sa.String(length=32), server_default="member", nullable=False),
            sa.Column("work_email", sa.String(length=255), nullable=True),
            sa.Column("is_verified_employee", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("has_multisport_card", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint("organization_id", "user_id", name="uq_org_members_org_user"),
        )
        op.create_index("ix_organization_members_id", "organization_members", ["id"])
        op.create_index(
            "ix_organization_members_organization_id", "organization_members", ["organization_id"]
        )
        op.create_index("ix_organization_members_user_id", "organization_members", ["user_id"])

    if "shadow_identity_vault" not in existing_tables:
        op.create_table(
            "shadow_identity_vault",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("original_user_id", sa.BigInteger(), nullable=False),
            sa.Column("organization_id", sa.Integer(), nullable=True),
            sa.Column("chat_id", sa.BigInteger(), nullable=True),
            sa.Column("encrypted_payload", sa.String(), nullable=False),
            sa.Column("anonymized_alias", sa.String(length=128), nullable=False),
            sa.Column("archived_reason", sa.String(length=64), server_default="gdpr_erasure", nullable=False),
            sa.Column("archived_by_user_id", sa.BigInteger(), nullable=True),
            sa.Column(
                "archived_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index("ix_shadow_identity_vault_id", "shadow_identity_vault", ["id"])
        op.create_index(
            "ix_shadow_identity_vault_original_user_id",
            "shadow_identity_vault",
            ["original_user_id"],
        )
        op.create_index(
            "ix_shadow_identity_vault_organization_id",
            "shadow_identity_vault",
            ["organization_id"],
        )
        op.create_index(
            "ix_shadow_identity_vault_chat_id",
            "shadow_identity_vault",
            ["chat_id"],
        )

    if "chats" in existing_tables:
        chat_cols = {c["name"] for c in inspector.get_columns("chats")}
        if "organization_id" not in chat_cols:
            op.add_column(
                "chats",
                sa.Column(
                    "organization_id",
                    sa.Integer(),
                    sa.ForeignKey("organizations.id", ondelete="SET NULL"),
                    nullable=True,
                ),
            )
            op.create_index("ix_chats_organization_id", "chats", ["organization_id"])

    if "users" in existing_tables:
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        if "has_multisport_card" not in user_cols:
            op.add_column(
                "users",
                sa.Column(
                    "has_multisport_card",
                    sa.Boolean(),
                    server_default=sa.text("false"),
                    nullable=False,
                ),
            )
        if "is_anonymized" not in user_cols:
            op.add_column(
                "users",
                sa.Column(
                    "is_anonymized",
                    sa.Boolean(),
                    server_default=sa.text("false"),
                    nullable=False,
                ),
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "users" in existing_tables:
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        if "is_anonymized" in user_cols:
            op.drop_column("users", "is_anonymized")
        if "has_multisport_card" in user_cols:
            op.drop_column("users", "has_multisport_card")

    if "chats" in existing_tables:
        chat_cols = {c["name"] for c in inspector.get_columns("chats")}
        if "organization_id" in chat_cols:
            op.drop_index("ix_chats_organization_id", table_name="chats")
            op.drop_column("chats", "organization_id")

    if "shadow_identity_vault" in existing_tables:
        op.drop_table("shadow_identity_vault")

    if "organization_members" in existing_tables:
        op.drop_table("organization_members")

    if "organizations" in existing_tables:
        op.drop_table("organizations")
