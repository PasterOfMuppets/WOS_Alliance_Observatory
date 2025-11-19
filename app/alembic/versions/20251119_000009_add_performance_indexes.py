"""Add performance indexes for common query patterns

Revision ID: 20251119_000009
Revises: 20251119_000008
Create Date: 2025-11-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251119_000009'
down_revision = '20251119_000008'
branch_labels = None
depends_on = None


def upgrade():
    # Contribution snapshots: frequently queried by alliance and week
    op.create_index(
        'idx_contribution_week_alliance',
        'contribution_snapshots',
        ['alliance_id', 'week_start_date']
    )

    # Bear scores: frequently joined with events and filtered by player
    # Note: individual indexes already exist, but composite helps for complex queries
    op.create_index(
        'idx_bear_scores_event_player',
        'bear_scores',
        ['bear_event_id', 'player_id']
    )

    # Power history: time-series queries for player timeline
    op.create_index(
        'idx_power_history_player_time',
        'player_power_history',
        ['player_id', 'captured_at']
    )

    # Furnace history: time-series queries for player timeline
    op.create_index(
        'idx_furnace_history_player_time',
        'player_furnace_history',
        ['player_id', 'captured_at']
    )

    # Foundry results: frequently queried by event and player
    op.create_index(
        'idx_foundry_results_event_player',
        'foundry_results',
        ['foundry_event_id', 'player_id']
    )

    # Foundry signups: frequently queried by event and player
    op.create_index(
        'idx_foundry_signups_event_player',
        'foundry_signups',
        ['foundry_event_id', 'player_id']
    )

    # AC signups: frequently queried by event (already has unique constraint, but explicit index helps)
    # Note: unique constraint automatically creates index, so this may be redundant
    # but doesn't hurt to be explicit

    # Alliance power snapshots: queried by date
    op.create_index(
        'idx_alliance_power_snapshot_date',
        'alliance_power_snapshots',
        ['snapshot_date']
    )


def downgrade():
    # Remove all indexes in reverse order
    op.drop_index('idx_alliance_power_snapshot_date', table_name='alliance_power_snapshots')
    op.drop_index('idx_foundry_signups_event_player', table_name='foundry_signups')
    op.drop_index('idx_foundry_results_event_player', table_name='foundry_results')
    op.drop_index('idx_furnace_history_player_time', table_name='player_furnace_history')
    op.drop_index('idx_power_history_player_time', table_name='player_power_history')
    op.drop_index('idx_bear_scores_event_player', table_name='bear_scores')
    op.drop_index('idx_contribution_week_alliance', table_name='contribution_snapshots')
