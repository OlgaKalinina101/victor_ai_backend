from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251106_create_walk_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'walk_sessions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('account_id', sa.String(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('distance_m', sa.Float(), nullable=True),
        sa.Column('steps', sa.Integer(), nullable=True),
        sa.Column('mode', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True)
    )

    op.create_table(
        'step_points',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('session_id', sa.Integer, sa.ForeignKey('walk_sessions.id', ondelete='CASCADE')),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lon', sa.Float(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'poi_visits',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('session_id', sa.Integer, sa.ForeignKey('walk_sessions.id', ondelete='CASCADE')),
        sa.Column('poi_id', sa.Integer, nullable=False),
        sa.Column('poi_name', sa.String(), nullable=False),
        sa.Column('distance_from_start', sa.Float(), nullable=True),
        sa.Column('found_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'achievements',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('unlocked_at', sa.DateTime(), nullable=True),
        sa.Column('type', sa.String(), nullable=True),
        sa.Column('icon', sa.String(), nullable=True)
    )

    op.create_table(
        'streaks',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('account_id', sa.String(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('last_active_date', sa.Date(), nullable=False),
        sa.Column('current_length', sa.Integer(), nullable=False, default=0),
        sa.Column('longest_streak', sa.Integer(), nullable=False, default=0)
    )

    op.create_table(
        'journal_entries',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('session_id', sa.Integer, sa.ForeignKey('walk_sessions.id', ondelete='CASCADE')),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('photo_path', sa.String(), nullable=True),
        sa.Column('poi_id', sa.Integer, nullable=True),
        sa.Column('poi_name', sa.String(), nullable=True)
    )


def downgrade():
    op.drop_table('journal_entries')
    op.drop_table('streaks')
    op.drop_table('achievements')
    op.drop_table('poi_visits')
    op.drop_table('step_points')
    op.drop_table('walk_sessions')
