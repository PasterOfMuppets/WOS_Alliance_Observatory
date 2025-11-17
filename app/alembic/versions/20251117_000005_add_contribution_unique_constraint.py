"""Add unique constraint to contribution_snapshots to prevent duplicates

Revision ID: 20251117_000005
Revises: 20251116_000004
Create Date: 2025-11-17

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251117_000005'
down_revision = '20251116_000004'
branch_labels = None
depends_on = None


def upgrade():
    # Normalize all existing snapshot_date and week_start_date to midnight UTC
    # This ensures that multiple uploads on the same day are properly deduplicated
    op.execute("""
        UPDATE contribution_snapshots
        SET snapshot_date = datetime(date(snapshot_date)),
            week_start_date = datetime(date(week_start_date))
    """)

    # Delete duplicate contribution_snapshots, keeping the earliest created_at for each
    # (alliance_id, player_id, week_start_date, snapshot_date)
    # This is a SQLite-compatible approach
    op.execute("""
        DELETE FROM contribution_snapshots
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM contribution_snapshots
            GROUP BY alliance_id, player_id, week_start_date, snapshot_date
        )
    """)

    # Add unique constraint to contribution_snapshots
    op.create_unique_constraint(
        'uq_contribution_snapshot',
        'contribution_snapshots',
        ['alliance_id', 'player_id', 'week_start_date', 'snapshot_date']
    )


def downgrade():
    # Remove unique constraint
    op.drop_constraint('uq_contribution_snapshot', 'contribution_snapshots', type_='unique')
