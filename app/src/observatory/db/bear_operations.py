"""Database operations for bear events."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models

logger = logging.getLogger(__name__)


def find_or_create_bear_event(
    session: Session,
    alliance_id: int,
    trap_id: int,
    started_at: datetime,
    ended_at: datetime | None = None,
    rally_count: int | None = None,
    total_damage: int | None = None,
) -> models.BearEvent:
    """
    Find or create a bear event.

    Args:
        session: Database session
        alliance_id: Alliance ID
        trap_id: Trap ID (1 or 2)
        started_at: When the bear trap started (UTC)
        ended_at: When the bear trap ended (UTC), optional
        rally_count: Number of rallies, optional
        total_damage: Total alliance damage, optional

    Returns:
        BearEvent model instance
    """
    # Try to find existing event
    stmt = select(models.BearEvent).where(
        models.BearEvent.alliance_id == alliance_id,
        models.BearEvent.trap_id == trap_id,
        models.BearEvent.started_at == started_at,
    )
    event = session.execute(stmt).scalar_one_or_none()

    if event is None:
        # Create new event
        event = models.BearEvent(
            alliance_id=alliance_id,
            trap_id=trap_id,
            started_at=started_at,
            ended_at=ended_at,
            rally_count=rally_count,
            total_damage=total_damage,
        )
        session.add(event)
        session.flush()  # Ensure event.id is available
        logger.info(f"Created new bear event: Trap {trap_id} at {started_at}")
    else:
        # Update stats if provided
        if ended_at is not None:
            event.ended_at = ended_at
        if rally_count is not None:
            event.rally_count = rally_count
        if total_damage is not None:
            event.total_damage = total_damage
        logger.debug(f"Updated bear event: ID {event.id}")

    return event


def add_bear_score(
    session: Session,
    bear_event_id: int,
    player_id: int,
    score: int,
    rank: int | None,
    recorded_at: datetime,
) -> models.BearScore:
    """
    Add a bear score record for a player.

    Args:
        session: Database session
        bear_event_id: Bear event ID
        player_id: Player ID
        score: Damage points
        rank: Rank (1, 2, 3, etc., or None if unranked)
        recorded_at: When the screenshot was taken (UTC)

    Returns:
        BearScore model instance
    """
    bear_score = models.BearScore(
        bear_event_id=bear_event_id,
        player_id=player_id,
        score=score,
        rank=rank,
        recorded_at=recorded_at,
    )
    session.add(bear_score)
    logger.debug(f"Added bear score for player {player_id}: {score} (rank {rank})")
    return bear_score


def save_bear_event_ocr(
    session: Session,
    alliance_id: int,
    trap_id: int,
    started_at: datetime,
    players_data: list[dict[str, Any]],
    recorded_at: datetime,
) -> dict[str, int]:
    """
    Save bear event OCR results to database.
    Creates/finds bear event and adds score records.

    Args:
        session: Database session
        alliance_id: Alliance ID
        trap_id: Trap ID (1 or 2)
        started_at: When the bear trap started (UTC)
        players_data: List of player dicts with name, damage_points, rank
        recorded_at: When the screenshot was taken (UTC)

    Returns:
        Dict with counts: {"event_id": N, "scores": M}
    """
    # Find or create the bear event
    bear_event = find_or_create_bear_event(session, alliance_id, trap_id, started_at)

    score_count = 0

    for player_data in players_data:
        name = player_data.get("name")
        if not name:
            continue

        # Strip alliance tag for player matching
        # e.g., "[HEI]Valorin" -> "Valorin"
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
            logger.warning(f"Player not found: {player_name} (from {name}), skipping bear score")
            continue

        damage_points = player_data.get("damage_points", 0)
        rank = player_data.get("rank")

        # Add bear score
        add_bear_score(
            session,
            bear_event_id=bear_event.id,
            player_id=player.id,
            score=damage_points,
            rank=rank,
            recorded_at=recorded_at,
        )
        score_count += 1

    session.commit()
    logger.info(f"Saved bear event scores: {score_count} scores for event {bear_event.id}")

    return {
        "event_id": bear_event.id,
        "scores": score_count,
    }
