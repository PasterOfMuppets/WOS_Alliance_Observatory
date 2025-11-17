"""Database operations for contribution snapshots."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models

logger = logging.getLogger(__name__)


def save_contribution_snapshot_ocr(
    session: Session,
    alliance_id: int,
    week_start_date: datetime,
    snapshot_date: datetime,
    players_data: list[dict[str, Any]],
    recorded_at: datetime,
) -> dict[str, int]:
    """
    Save contribution snapshot OCR results to database.

    Args:
        session: Database session
        alliance_id: Alliance ID
        week_start_date: Week start date (Monday, UTC)
        snapshot_date: Date of this snapshot (which day of week, UTC)
        players_data: List of player dicts with rank, name, contribution
        recorded_at: When the screenshot was taken (UTC)

    Returns:
        Dict with count: {"snapshots": N}
    """
    # Normalize dates to midnight UTC to prevent duplicates from different upload times
    week_start_date = week_start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    snapshot_date = snapshot_date.replace(hour=0, minute=0, second=0, microsecond=0)

    snapshot_count = 0

    for player_data in players_data:
        name = player_data.get("name")
        if not name:
            continue

        # Strip alliance tag for player matching
        player_name = name
        if player_name.startswith("[") and "]" in player_name:
            player_name = player_name.split("]", 1)[1].strip()

        # Find player in database
        stmt = select(models.Player).where(
            models.Player.alliance_id == alliance_id,
            models.Player.name == player_name
        )
        player = session.execute(stmt).scalar_one_or_none()

        if player is None:
            logger.warning(f"Player not found: {player_name} (from {name}), skipping contribution")
            continue

        contribution_amount = player_data.get("contribution", 0)
        rank = player_data.get("rank")

        # Check if snapshot already exists
        stmt = select(models.ContributionSnapshot).where(
            models.ContributionSnapshot.alliance_id == alliance_id,
            models.ContributionSnapshot.player_id == player.id,
            models.ContributionSnapshot.week_start_date == week_start_date,
            models.ContributionSnapshot.snapshot_date == snapshot_date,
        )
        existing = session.execute(stmt).scalar_one_or_none()

        if existing:
            logger.debug(f"Contribution snapshot already exists for {player_name} on {snapshot_date.date()}")
            continue

        # Add contribution snapshot
        snapshot = models.ContributionSnapshot(
            alliance_id=alliance_id,
            player_id=player.id,
            week_start_date=week_start_date,
            snapshot_date=snapshot_date,
            contribution_amount=contribution_amount,
            rank=rank,
            recorded_at=recorded_at,
        )
        session.add(snapshot)
        logger.debug(f"Added contribution for {player_name}: {contribution_amount} (rank {rank})")
        snapshot_count += 1

    session.commit()
    logger.info(f"Saved {snapshot_count} contribution snapshots for {snapshot_date.date()}")

    return {
        "snapshots": snapshot_count,
    }
