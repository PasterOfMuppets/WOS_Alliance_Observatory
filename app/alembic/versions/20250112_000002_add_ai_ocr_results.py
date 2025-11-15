"""Add ai_ocr_results table"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20250112_000002"
down_revision = "20231112_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_ocr_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("screenshot_path", sa.String(length=512), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("card_count", sa.Integer(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("ai_ocr_results")
