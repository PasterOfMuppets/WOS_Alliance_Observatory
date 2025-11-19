"""Database operations for Alliance Championship (AC) events."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models

logger = logging.getLogger(__name__)


def find_or_create_ac_event(
    session: Session,
    alliance_id: int,
    week_start_date: datetime,
    total_registered: int | None = None,
    total_power: int | None = None,
) -> models.ACEvent:
    """
    Find or create an AC event.

    Args:
        session: Database session
        alliance_id: Alliance ID
        week_start_date: Week start date (Monday of AC week, UTC)
        total_registered: Total number of registered players
        total_power: Total AC power

    Returns:
        ACEvent model instance
    """
    # Try to find existing event
    stmt = select(models.ACEvent).where(
        models.ACEvent.alliance_id == alliance_id,
        models.ACEvent.week_start_date == week_start_date,
    )
    event = session.execute(stmt).scalar_one_or_none()

    if event is None:
        # Create new event
        event = models.ACEvent(
            alliance_id=alliance_id,
            week_start_date=week_start_date,
            total_registered=total_registered,
            total_power=total_power,
        )
        session.add(event)
        session.flush()  # Ensure event.id is available
        logger.info(f"Created new AC event: Week of {week_start_date.date()}")
    else:
        # Update stats if provided
        if total_registered is not None:
            event.total_registered = total_registered
        if total_power is not None:
            event.total_power = total_power
        logger.debug(f"Updated AC event: ID {event.id}")

    return event


def add_ac_signup(
    session: Session,
    ac_event_id: int,
    player_id: int,
    ac_power: int,
    recorded_at: datetime,
) -> models.ACSignup:
    """
    Add an AC signup record for a player.

    Args:
        session: Database session
        ac_event_id: AC event ID
        player_id: Player ID
        ac_power: Player's AC power
        recorded_at: When the screenshot was taken (UTC)

    Returns:
        ACSignup model instance
    """
    signup = models.ACSignup(
        ac_event_id=ac_event_id,
        player_id=player_id,
        ac_power=ac_power,
        recorded_at=recorded_at,
    )
    session.add(signup)
    logger.debug(f"Added AC signup for player {player_id}: power={ac_power}")
    return signup


def save_ac_signup_ocr(
    session: Session,
    alliance_id: int,
    week_start_date: datetime,
    signup_data: dict[str, Any],
    recorded_at: datetime,
) -> dict[str, int]:
    """
    Save AC signup OCR results to database.
    Creates/finds AC event and adds signup records.

    Args:
        session: Database session
        alliance_id: Alliance ID
        week_start_date: Week start date (Monday of AC week, UTC)
        signup_data: Dict with total_registered, total_power, players
        recorded_at: When the screenshot was taken (UTC)

    Returns:
        Dict with counts: {"event_id": N, "signups": M}
    """
    # Extract header stats
    total_registered = signup_data.get("total_registered")
    total_power = signup_data.get("total_power")
    players_data = signup_data.get("players", [])

    # Find or create the AC event
    ac_event = find_or_create_ac_event(
        session,
        alliance_id=alliance_id,
        week_start_date=week_start_date,
        total_registered=total_registered,
        total_power=total_power,
    )

    signup_count = 0

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
            logger.warning(f"Player not found: {player_name} (from {name}), skipping AC signup")
            continue

        ac_power = player_data.get("ac_power", 0)

        # Check if signup already exists
        existing_signup_stmt = select(models.ACSignup).where(
            models.ACSignup.ac_event_id == ac_event.id,
            models.ACSignup.player_id == player.id,
        )
        existing_signup = session.execute(existing_signup_stmt).scalar_one_or_none()

        if existing_signup is not None:
            # Update AC power if new value is higher
            if ac_power > existing_signup.ac_power:
                logger.info(
                    f"Updating AC signup for player {player_name}: "
                    f"{existing_signup.ac_power} -> {ac_power}"
                )
                existing_signup.ac_power = ac_power
                existing_signup.recorded_at = recorded_at
            else:
                logger.debug(f"Skipping duplicate AC signup for player {player_name}")
        else:
            # Add new AC signup
            add_ac_signup(
                session,
                ac_event_id=ac_event.id,
                player_id=player.id,
                ac_power=ac_power,
                recorded_at=recorded_at,
            )
            signup_count += 1

    session.commit()
    logger.info(f"Saved AC signups: {signup_count} signups for event {ac_event.id}")

    return {
        "event_id": ac_event.id,
        "signups": signup_count,
    }
