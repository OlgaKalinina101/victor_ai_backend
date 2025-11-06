"""add emotion fields to poi_visits

Revision ID: 490c7bad6288
Revises: 48c3fb148d26
Create Date: 2025-11-06 02:41:36.514971

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2a1f9c0e2ab'
down_revision = '48c3fb148d26'  # <-- поставь ID твоей предыдущей миграции!
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('poi_visits', sa.Column('emotion_emoji', sa.String(), nullable=True))
    op.add_column('poi_visits', sa.Column('emotion_label', sa.String(), nullable=True))
    op.add_column('poi_visits', sa.Column('emotion_color', sa.String(), nullable=True))


def downgrade():
    op.drop_column('poi_visits', 'emotion_color')
    op.drop_column('poi_visits', 'emotion_label')
    op.drop_column('poi_visits', 'emotion_emoji')
