"""fix_kavci_hory_locations

Revision ID: cab7ed4fc677
Revises: 2e555b9cd60a
Create Date: 2026-04-27 10:53:14.049883

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cab7ed4fc677'
down_revision: Union[str, Sequence[str], None] = '2e555b9cd60a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Fix Draft #10 (28.03) and Draft #11 (04.04)
    # The user provided the address: https://maps.app.goo.gl/Sef5csEqQHYLfYNP7?g_st=ic
    location_str = "Kavčí hory"
    
    op.execute(f"""
        UPDATE games 
        SET location = '{location_str}'
        WHERE date_time::date IN ('2026-03-28', '2026-04-04')
    """)


def downgrade() -> None:
    pass
