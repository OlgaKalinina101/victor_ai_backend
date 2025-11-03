"""new feature

Revision ID: 5bb1e2a339ad
Revises: b0d4e919f5c4
Create Date: 2025-11-02 22:19:11.132110

"""

revision = '5bb1e2a339ad'
down_revision = 'b0d4e919f5c4'
branch_labels = None
depends_on = None

from typing import Sequence, Union

import geoalchemy2
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
def upgrade() -> None:
    """Upgrade schema - keep osm_elements, drop old tables."""

    # === ДРОПАЕМ СТАРЫЕ ТАБЛИЦЫ ===
    op.drop_table('place_tags')
    op.drop_table('tags')

    # Дропаем индексы places (если есть)
    op.drop_index(op.f('idx_places_geom'), table_name='places', if_exists=True)
    op.drop_index(op.f('idx_places_polygon'), table_name='places', if_exists=True)
    op.drop_index(op.f('ix_places_name'), table_name='places', if_exists=True)
    op.drop_index(op.f('ix_places_osm_id'), table_name='places', if_exists=True)
    op.drop_table('places')

    # Дропаем regions
    op.drop_index(op.f('idx_regions_bbox'), table_name='regions', if_exists=True)
    op.drop_index(op.f('ix_regions_name'), table_name='regions', if_exists=True)
    op.drop_table('regions')

    # === СОЗДАЁМ/ОБНОВЛЯЕМ НАШУ ТАБЛИЦУ osm_elements ===
    op.create_table('osm_elements',
                    sa.Column('id', sa.BigInteger(), nullable=False),
                    sa.Column('type', sa.String(length=10), nullable=False),
                    sa.Column('tags', sa.JSON(), nullable=True),
                    sa.Column('geometry', geoalchemy2.types.Geometry(geometry_type='GEOMETRY', srid=4326),
                              nullable=True),
                    sa.PrimaryKeyConstraint('id')
                    )

    # === ИНДЕКСЫ ДЛЯ СКОРОСТИ ===
    op.create_index('idx_osm_elements_geometry', 'osm_elements', ['geometry'],
                    postgresql_using='gist', if_not_exists=True)
    op.create_index('idx_osm_elements_type', 'osm_elements', ['type'],
                    postgresql_using='btree', if_not_exists=True)


def downgrade() -> None:
    """Downgrade - restore old tables, drop osm_elements."""

    # === ДРОПАЕМ НАШУ ТАБЛИЦУ ===
    op.drop_index('idx_osm_elements_geometry', table_name='osm_elements')
    op.drop_index('idx_osm_elements_type', table_name='osm_elements')
    op.drop_table('osm_elements')
