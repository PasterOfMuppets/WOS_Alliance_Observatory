"""Add unique constraint to ac_signups to prevent duplicates

Revision ID: 20251119_000006
Revises: 20251117_000005
Create Date: 2025-11-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251119_000006'
down_revision = '20251117_000005'
branch_labels = None
depends_on = None


def upgrade():
    # Delete duplicate AC signups, keeping the one with highest ac_power for each
    # (ac_event_id, player_id) combination
    # This is a SQLite-compatible approach using subquery
    op.execute("""
        DELETE FROM ac_signups
        WHERE id NOT IN (
            SELECT MAX(id)
            FROM ac_signups
            GROUP BY ac_event_id, player_id
            HAVING ac_power = MAX(ac_power)
        )
    """)

    # Clean up any remaining duplicates by keeping first id
    op.execute("""
        DELETE FROM ac_signups
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM ac_signups
            GROUP BY ac_event_id, player_id
        )
    """)

    # Add unique constraint to ac_signups
    op.create_unique_constraint(
        'uq_ac_signup',
        'ac_signups',
        ['ac_event_id', 'player_id']
    )


def downgrade():
    # Remove unique constraint
    op.drop_constraint('uq_ac_signup', 'ac_signups', type_='unique')
