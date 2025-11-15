"""Add created_at to dialogue_history

Revision ID: 20251115_add_created_at
Revises: 2f495d480ffe
Create Date: 2025-11-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20251115_add_created_at'
down_revision: Union[str, Sequence[str], None] = '2f495d480ffe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Добавляем колонку created_at
    op.add_column('dialogue_history',
        sa.Column('created_at', sa.DateTime(), nullable=True)
    )

    # Устанавливаем значение по умолчанию для существующих записей
    op.execute("UPDATE dialogue_history SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")

    # Делаем колонку NOT NULL после заполнения данных
    op.alter_column('dialogue_history', 'created_at', nullable=False)

    # Создаем индексы для быстрой пагинации
    op.create_index('idx_account_created_desc', 'dialogue_history', ['account_id', 'created_at'])
    op.create_index('idx_account_id_desc', 'dialogue_history', ['account_id', 'id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Удаляем индексы
    op.drop_index('idx_account_id_desc', table_name='dialogue_history')
    op.drop_index('idx_account_created_desc', table_name='dialogue_history')

    # Удаляем колонку
    op.drop_column('dialogue_history', 'created_at')
