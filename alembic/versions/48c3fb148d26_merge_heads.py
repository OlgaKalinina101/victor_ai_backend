"""merge heads

Revision ID: 48c3fb148d26
Revises: 20251106_create_walk_tables, 5bb1e2a339ad
Create Date: 2025-11-06 02:10:09.207044

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '48c3fb148d26'
down_revision: Union[str, Sequence[str], None] = ('20251106_create_walk_tables', '5bb1e2a339ad')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
