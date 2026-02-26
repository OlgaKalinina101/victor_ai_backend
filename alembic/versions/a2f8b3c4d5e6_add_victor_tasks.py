# Victor AI - Personal AI Companion for Android
# Copyright (C) 2025-2026 Olga Kalinina

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.

"""Add victor_tasks table for autonomy

Revision ID: a2f8b3c4d5e6
Revises: 1e291a82539e
Create Date: 2026-02-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a2f8b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = '1e291a82539e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Enum types
victortasktrigger = postgresql.ENUM('TIME', 'NEXT_SESSION', 'MANUAL', name='victortasktrigger', create_type=False)
victortaskstatus = postgresql.ENUM('PENDING', 'DONE', 'CANCELLED', name='victortaskstatus', create_type=False)


def upgrade() -> None:
    # Create enum types
    victortasktrigger.create(op.get_bind(), checkfirst=True)
    victortaskstatus.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'victor_tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('account_id', sa.String(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('trigger_type', victortasktrigger, nullable=False, server_default='MANUAL'),
        sa.Column('trigger_value', sa.String(length=255), nullable=True),
        sa.Column('status', victortaskstatus, nullable=False, server_default='PENDING'),
        sa.Column('source', sa.String(length=50), nullable=False, server_default='reflection'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['chat_meta.account_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_victor_tasks_account_id', 'victor_tasks', ['account_id'])


def downgrade() -> None:
    op.drop_index('ix_victor_tasks_account_id', table_name='victor_tasks')
    op.drop_table('victor_tasks')
    victortaskstatus.drop(op.get_bind(), checkfirst=True)
    victortasktrigger.drop(op.get_bind(), checkfirst=True)
