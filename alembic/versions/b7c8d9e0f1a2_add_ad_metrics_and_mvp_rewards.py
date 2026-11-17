"""Add sponsor banner metrics, MVP reward claims, and 21 Coffee default sponsor banner

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f7
Create Date: 2026-11-17 12:02:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "chat_members" in existing_tables:
        cm_cols = [c["name"] for c in inspector.get_columns("chat_members")]
        if "loyalty_card_id" not in cm_cols:
            op.add_column(
                "chat_members",
                sa.Column("loyalty_card_id", sa.String(length=128), nullable=True),
            )

    if "ad_banners" in existing_tables:
        ad_cols = [c["name"] for c in inspector.get_columns("ad_banners")]
        new_ad_cols = [
            ("hero_image_url", sa.String(), None),
            ("title", sa.String(length=128), None),
            ("subtitle", sa.String(length=255), None),
            ("badge_text", sa.String(length=64), None),
            ("cta_text", sa.String(length=64), None),
            ("reward_title", sa.String(length=255), None),
            ("reward_instructions", sa.Text(), None),
            ("impressions_count", sa.Integer(), "0"),
            ("clicks_count", sa.Integer(), "0"),
        ]
        for col_name, col_type, server_def in new_ad_cols:
            if col_name not in ad_cols:
                op.add_column(
                    "ad_banners",
                    sa.Column(
                        col_name,
                        col_type,
                        nullable=(server_def is None),
                        server_default=server_def,
                    ),
                )

    if "ad_banner_events" not in existing_tables:
        op.create_table(
            "ad_banner_events",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column(
                "banner_id",
                sa.Integer(),
                sa.ForeignKey("ad_banners.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("chat_id", sa.BigInteger(), nullable=True),
            sa.Column("user_id", sa.BigInteger(), nullable=True),
            sa.Column("placement", sa.String(length=64), nullable=True),
            sa.Column("event_type", sa.String(length=16), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index("ix_ad_banner_events_banner_id", "ad_banner_events", ["banner_id"])
        op.create_index("ix_ad_banner_events_chat_id", "ad_banner_events", ["chat_id"])
        op.create_index("ix_ad_banner_events_event_type", "ad_banner_events", ["event_type"])

    if "mvp_reward_claims" not in existing_tables:
        op.create_table(
            "mvp_reward_claims",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("code", sa.String(length=32), nullable=False, unique=True),
            sa.Column(
                "chat_id",
                sa.BigInteger(),
                sa.ForeignKey("chats.chat_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "game_id",
                sa.Integer(),
                sa.ForeignKey("games.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("user_id", sa.BigInteger(), nullable=False),
            sa.Column(
                "banner_id",
                sa.Integer(),
                sa.ForeignKey("ad_banners.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("sponsor_name", sa.String(length=128), nullable=False),
            sa.Column("reward_title", sa.String(length=255), nullable=False),
            sa.Column("sponsor_url", sa.String(length=512), nullable=True),
            sa.Column("loyalty_identifier", sa.String(length=128), nullable=True),
            sa.Column(
                "status",
                sa.String(length=24),
                server_default="ISSUED",
                nullable=False,
            ),
            sa.Column(
                "issued_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("redeemed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_mvp_reward_claims_code", "mvp_reward_claims", ["code"], unique=True)
        op.create_index("ix_mvp_reward_claims_chat_id", "mvp_reward_claims", ["chat_id"])
        op.create_index("ix_mvp_reward_claims_user_id", "mvp_reward_claims", ["user_id"])

    # Seed default 21 Coffee (@21coffeecz) global sponsor banner if not present
    if "ad_banners" in existing_tables:
        existing = conn.execute(
            sa.text("SELECT id FROM ad_banners WHERE link LIKE '%21coffee%' LIMIT 1")
        ).fetchone()
        if not existing:
            conn.execute(
                sa.text(
                    """
                    INSERT INTO ad_banners (
                        image_url, hero_image_url, title, subtitle, badge_text, cta_text,
                        text, link, reward_title, reward_instructions,
                        impressions_count, clicks_count, is_active, show_probability, chat_id
                    ) VALUES (
                        '/web/assets/sponsors/21coffee_logo.jpg',
                        '/web/assets/sponsors/21coffee_hero.webp',
                        '21 Coffee • Specialty Coffee & Brunch',
                        '📍 Holešovice (Na Maninách 16) • Vinohrady (Londýnská)',
                        '☕ MVP PARTNER • FREE COFFEE',
                        '@21coffeecz ↗',
                        'Бесплатный спешелти-кофе каждому MVP матча от 21 Coffee!',
                        'https://www.instagram.com/21coffeecz/',
                        '1x Бесплатный кофе в 21 Coffee',
                        'Укажи свой номер телефона или ID карты лояльности (Apple Wallet / 21coffee.eu) для начисления бесплатного кофе, либо покажи этот цифровой MVP-пасс бариста на кассе (Na Maninách 1041/16 или Londýnská).',
                        0, 0, true, 100, NULL
                    )
                    """
                )
            )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "mvp_reward_claims" in existing_tables:
        op.drop_table("mvp_reward_claims")
    if "ad_banner_events" in existing_tables:
        op.drop_table("ad_banner_events")
