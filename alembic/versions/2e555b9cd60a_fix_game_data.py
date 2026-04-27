"""fix_game_data

Revision ID: 2e555b9cd60a
Revises: ba3d7e5c9f5f
Create Date: 2026-04-27 10:29:27.655192

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e555b9cd60a'
down_revision: Union[str, Sequence[str], None] = 'ba3d7e5c9f5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix Game 1
    op.execute("""
        UPDATE games 
        SET location = 'Sportovní centrum Prosek', 
            team_count = 3, 
            score_c = COALESCE(score_c, 0) 
        WHERE id = (SELECT id FROM games ORDER BY date_time ASC LIMIT 1)
    """)
    
    # Fix subsequent games
    op.execute("""
        UPDATE games 
        SET location = 'Plamínkové 1539, Praha 4-Nusle' 
        WHERE id IN (SELECT id FROM games ORDER BY date_time ASC LIMIT 100 OFFSET 1)
    """)


def downgrade() -> None:
    pass
