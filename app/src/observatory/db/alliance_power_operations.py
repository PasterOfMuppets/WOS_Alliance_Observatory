"""Database operations for alliance power snapshots."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from . import models

logger = logging.getLogger(__name__)


def save_alliance_power_snapshot_ocr(
    session: Session,
    snapshot_date: datetime,
    alliances_data: list[dict[str, Any]],
    recorded_at: datetime,
) -> dict[str, int]:
    """
    Save alliance power snapshot OCR results to database.

    Args:
        session: Database session
        snapshot_date: Date of this snapshot (UTC)
        alliances_data: List of alliance dicts with rank, alliance_name_with_tag, total_power
        recorded_at: When the screenshot was taken (UTC)

    Returns:
        Dict with count: {"snapshots": N}
    """
    snapshot_count = 0

    for alliance_data in alliances_data:
        alliance_name_with_tag = alliance_data.get("alliance_name_with_tag", "")
        if not alliance_name_with_tag:
            continue

        # Parse alliance tag and name
        # e.g., "[KIL]ShadowWarriors" -> tag="KIL", name="ShadowWarriors"
        alliance_tag = None
        alliance_name = alliance_name_with_tag

        if alliance_name_with_tag.startswith("[") and "]" in alliance_name_with_tag:
            parts = alliance_name_with_tag.split("]", 1)
            alliance_tag = parts[0][1:]  # Remove the leading [
            alliance_name = parts[1] if len(parts) > 1 else alliance_name_with_tag

        total_power = alliance_data.get("total_power", 0)
        rank = alliance_data.get("rank")

        # Add alliance power snapshot
        snapshot = models.AlliancePowerSnapshot(
            alliance_name=alliance_name,
            alliance_tag=alliance_tag,
            total_power=total_power,
            rank=rank,
            snapshot_date=snapshot_date,
            recorded_at=recorded_at,
        )
        session.add(snapshot)
        logger.debug(f"Added alliance power: Rank {rank} - [{alliance_tag}]{alliance_name}: {total_power:,}")
        snapshot_count += 1

    session.commit()
    logger.info(f"Saved {snapshot_count} alliance power snapshots for {snapshot_date.date()}")

    return {
        "snapshots": snapshot_count,
    }
