"""Initial schema with alliances, players, screenshots, and stats."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20231112_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alliances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False, unique=True),
        sa.Column("tag", sa.String(length=32), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "players",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alliance_id", sa.Integer(), sa.ForeignKey("alliances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("status", sa.Enum("active", "inactive", "retired", name="player_status"), nullable=False, server_default="active"),
        sa.Column("current_power", sa.Integer(), nullable=True),
        sa.Column("current_furnace", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("alliance_id", "name", name="uq_player_alliance_name"),
    )
    op.create_index("ix_players_alliance_id", "players", ["alliance_id"])

    op.create_table(
        "screenshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alliance_id", sa.Integer(), sa.ForeignKey("alliances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("uploader", sa.String(length=64), nullable=True),
        sa.Column("detected_type", sa.Enum(
            "unknown",
            "alliance_members",
            "contribution",
            "ac_lanes",
            "bear_event",
            name="screenshot_type",
        ), nullable=False, server_default="unknown"),
        sa.Column("status", sa.Enum("pending", "processing", "succeeded", "failed", name="screenshot_status"), nullable=False, server_default="pending"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("source_path", sa.String(length=256), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_screenshots_status", "screenshots", ["status"])

    op.create_table(
        "player_power_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("power", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("player_id", "captured_at", name="uq_power_capture"),
    )
    op.create_index("ix_player_power_history_player_id", "player_power_history", ["player_id"])
    op.create_index("ix_player_power_history_captured_at", "player_power_history", ["captured_at"])

    op.create_table(
        "player_furnace_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("furnace_level", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("player_id", "captured_at", name="uq_furnace_capture"),
    )
    op.create_index("ix_player_furnace_history_player_id", "player_furnace_history", ["player_id"])
    op.create_index("ix_player_furnace_history_captured_at", "player_furnace_history", ["captured_at"])

    op.create_table(
        "event_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("player_id", sa.Integer(), sa.ForeignKey("players.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.Enum("power", "furnace", "contribution", "bear", "custom", name="event_stat_type"), nullable=False),
        sa.Column("metric_name", sa.String(length=64), nullable=False),
        sa.Column("metric_value", sa.Numeric(18, 2), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_event_stats_player_id", "event_stats", ["player_id"])
    op.create_index("ix_event_stats_event_type", "event_stats", ["event_type"])
    op.create_index("ix_event_stats_captured_at", "event_stats", ["captured_at"])


def downgrade() -> None:
    op.drop_index("ix_event_stats_captured_at", table_name="event_stats")
    op.drop_index("ix_event_stats_event_type", table_name="event_stats")
    op.drop_index("ix_event_stats_player_id", table_name="event_stats")
    op.drop_table("event_stats")

    op.drop_index("ix_player_furnace_history_captured_at", table_name="player_furnace_history")
    op.drop_index("ix_player_furnace_history_player_id", table_name="player_furnace_history")
    op.drop_table("player_furnace_history")

    op.drop_index("ix_player_power_history_captured_at", table_name="player_power_history")
    op.drop_index("ix_player_power_history_player_id", table_name="player_power_history")
    op.drop_table("player_power_history")

    op.drop_index("ix_screenshots_status", table_name="screenshots")
    op.drop_table("screenshots")

    op.drop_index("ix_players_alliance_id", table_name="players")
    op.drop_table("players")

    op.drop_table("alliances")
