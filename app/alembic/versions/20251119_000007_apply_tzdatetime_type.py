"""Apply TZDateTime type to all datetime columns for proper timezone handling

Revision ID: 20251119_000007
Revises: 20251119_000006
Create Date: 2025-11-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251119_000007'
down_revision = '20251119_000006'
branch_labels = None
depends_on = None


def upgrade():
    # Note: TZDateTime is a TypeDecorator that doesn't change the database schema
    # but changes how values are processed. This migration is primarily for documentation
    # and to ensure any naive datetimes are converted to timezone-aware format.

    # For SQLite, we need to ensure all datetime strings have timezone info
    # The TZDateTime type will handle this automatically going forward, but we
    # should clean up any existing data that might be missing timezone info.

    # List of tables and their datetime columns to ensure proper format
    tables_and_columns = [
        ('users', ['created_at', 'last_login']),
        ('alliances', ['created_at']),
        ('players', ['created_at', 'updated_at']),
        ('screenshots', ['processed_at', 'created_at']),
        ('player_power_history', ['captured_at', 'created_at']),
        ('player_furnace_history', ['captured_at', 'created_at']),
        ('event_stats', ['captured_at']),
        ('bear_events', ['started_at', 'ended_at', 'created_at']),
        ('bear_scores', ['recorded_at', 'created_at']),
        ('foundry_events', ['event_date', 'created_at']),
        ('foundry_signups', ['recorded_at', 'created_at']),
        ('foundry_results', ['recorded_at', 'created_at']),
        ('ac_events', ['week_start_date', 'created_at']),
        ('ac_signups', ['recorded_at', 'created_at']),
        ('contribution_snapshots', ['week_start_date', 'snapshot_date', 'recorded_at', 'created_at']),
        ('alliance_power_snapshots', ['snapshot_date', 'recorded_at', 'created_at']),
    ]

    # For each table and column, ensure timezone-aware format
    for table_name, columns in tables_and_columns:
        for column in columns:
            # Add +00:00 timezone suffix if not present (assumes UTC)
            # Skip if column is NULL
            op.execute(f"""
                UPDATE {table_name}
                SET {column} = {column} || '+00:00'
                WHERE {column} IS NOT NULL
                  AND {column} NOT LIKE '%+%'
                  AND {column} NOT LIKE '%Z'
            """)


def downgrade():
    # No downgrade needed - TZDateTime is backward compatible
    # The timezone suffixes don't break DateTime(timezone=True)
    pass
