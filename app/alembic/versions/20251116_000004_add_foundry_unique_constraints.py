"""Add unique constraints to foundry_signups and foundry_results to prevent duplicates

Revision ID: 20251116_000004
Revises: 20251115_000003
Create Date: 2025-11-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251116_000004'
down_revision = '20251115_000003'
branch_labels = None
depends_on = None


def upgrade():
    # Delete duplicate foundry_signups, keeping the earliest created_at for each (foundry_event_id, player_id)
    # This is a SQLite-compatible approach
    op.execute("""
        DELETE FROM foundry_signups
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM foundry_signups
            GROUP BY foundry_event_id, player_id
        )
    """)

    # Delete duplicate foundry_results, keeping the earliest created_at for each (foundry_event_id, player_id)
    op.execute("""
        DELETE FROM foundry_results
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM foundry_results
            GROUP BY foundry_event_id, player_id
        )
    """)

    # Add unique constraint to foundry_signups
    op.create_unique_constraint(
        'uq_foundry_signup_event_player',
        'foundry_signups',
        ['foundry_event_id', 'player_id']
    )

    # Add unique constraint to foundry_results
    op.create_unique_constraint(
        'uq_foundry_result_event_player',
        'foundry_results',
        ['foundry_event_id', 'player_id']
    )


def downgrade():
    # Remove unique constraints
    op.drop_constraint('uq_foundry_result_event_player', 'foundry_results', type_='unique')
    op.drop_constraint('uq_foundry_signup_event_player', 'foundry_signups', type_='unique')
