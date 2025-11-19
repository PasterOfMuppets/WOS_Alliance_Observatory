"""Add notes field to bear_events table

Revision ID: 20251119_000008
Revises: 20251119_000007
Create Date: 2025-11-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251119_000008'
down_revision = '20251119_000007'
branch_labels = None
depends_on = None


def upgrade():
    # Add notes column to bear_events table
    op.add_column('bear_events', sa.Column('notes', sa.Text(), nullable=True))


def downgrade():
    # Remove notes column
    op.drop_column('bear_events', 'notes')
