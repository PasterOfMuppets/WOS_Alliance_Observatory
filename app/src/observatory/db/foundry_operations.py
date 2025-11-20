"""Database operations for foundry events."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .player_matching import find_player_with_fuzzy_fallback

logger = logging.getLogger(__name__)


def find_or_create_foundry_event(
    session: Session,
    alliance_id: int,
    legion_number: int,
    event_date: datetime,
    total_troop_power: int | None = None,
    max_participants: int | None = None,
    actual_participants: int | None = None,
) -> models.FoundryEvent:
    """
    Find or create a foundry event.

    Args:
        session: Database session
        alliance_id: Alliance ID
        legion_number: Legion number (1 or 2)
        event_date: When the foundry event occurs (UTC)
        total_troop_power: Total troop power from signup screen
        max_participants: Maximum participants allowed
        actual_participants: Number who actually signed up

    Returns:
        FoundryEvent model instance
    """
    # Try to find existing event
    stmt = select(models.FoundryEvent).where(
        models.FoundryEvent.alliance_id == alliance_id,
        models.FoundryEvent.legion_number == legion_number,
        models.FoundryEvent.event_date == event_date,
    )
    event = session.execute(stmt).scalar_one_or_none()

    if event is None:
        # Create new event
        event = models.FoundryEvent(
            alliance_id=alliance_id,
            legion_number=legion_number,
            event_date=event_date,
            total_troop_power=total_troop_power,
            max_participants=max_participants,
            actual_participants=actual_participants,
        )
        session.add(event)
        session.flush()  # Ensure event.id is available
        logger.info(f"Created new foundry event: Legion {legion_number} at {event_date}")
    else:
        # Update stats if provided
        if total_troop_power is not None:
            event.total_troop_power = total_troop_power
        if max_participants is not None:
            event.max_participants = max_participants
        if actual_participants is not None:
            event.actual_participants = actual_participants
        logger.debug(f"Updated foundry event: ID {event.id}")

    return event


def add_foundry_signup(
    session: Session,
    foundry_event_id: int,
    player_id: int,
    foundry_power: int,
    voted: bool,
    recorded_at: datetime,
) -> models.FoundrySignup | None:
    """
    Add a foundry signup record for a player.
    Skips if a record already exists for this player in this event.

    Args:
        session: Database session
        foundry_event_id: Foundry event ID
        player_id: Player ID
        foundry_power: Player's foundry power
        voted: Whether the player voted
        recorded_at: When the screenshot was taken (UTC)

    Returns:
        FoundrySignup model instance or None if already exists
    """
    # Check if record already exists
    stmt = select(models.FoundrySignup).where(
        models.FoundrySignup.foundry_event_id == foundry_event_id,
        models.FoundrySignup.player_id == player_id,
    )
    existing = session.execute(stmt).scalar_one_or_none()

    if existing:
        logger.debug(f"Foundry signup already exists for player {player_id} in event {foundry_event_id}")
        return None

    signup = models.FoundrySignup(
        foundry_event_id=foundry_event_id,
        player_id=player_id,
        foundry_power=foundry_power,
        voted=voted,
        recorded_at=recorded_at,
    )
    session.add(signup)
    logger.debug(f"Added foundry signup for player {player_id}: power={foundry_power}, voted={voted}")
    return signup


def save_foundry_signup_ocr(
    session: Session,
    alliance_id: int,
    legion_number: int,
    event_date: datetime,
    signup_data: dict[str, Any],
    recorded_at: datetime,
    screenshot_filename: str | None = None,
) -> dict[str, int]:
    """
    Save foundry signup OCR results to database.
    Creates/finds foundry event and adds signup records.

    Args:
        session: Database session
        alliance_id: Alliance ID
        legion_number: Legion number (1 or 2)
        event_date: When the foundry event occurs (UTC)
        signup_data: Dict with legion_number, total_troop_power, players, etc.
        recorded_at: When the screenshot was taken (UTC)
        screenshot_filename: Optional filename of the screenshot for logging

    Returns:
        Dict with counts: {"event_id": N, "signups": M}
    """
    # Extract header stats
    total_troop_power = signup_data.get("total_troop_power")
    max_participants = signup_data.get("max_participants")
    actual_participants = signup_data.get("actual_participants")
    players_data = signup_data.get("players", [])

    # Find or create the foundry event
    foundry_event = find_or_create_foundry_event(
        session,
        alliance_id=alliance_id,
        legion_number=legion_number,
        event_date=event_date,
        total_troop_power=total_troop_power,
        max_participants=max_participants,
        actual_participants=actual_participants,
    )

    signup_count = 0

    for player_data in players_data:
        name = player_data.get("name")
        status = player_data.get("status")

        if not name:
            continue

        # Only process players who joined THIS legion
        # Skip "legion_2_dispatched" and "no_engagements"
        if status != "join":
            logger.debug(f"Skipping {name}: status={status}")
            continue

        # Strip alliance tag for player matching (similar to bear events)
        # e.g., "[HEI]Valorin" -> "Valorin"
        player_name = name
        if player_name.startswith("[") and "]" in player_name:
            player_name = player_name.split("]", 1)[1].strip()

        # Find player in database (with fuzzy matching fallback)
        player = find_player_with_fuzzy_fallback(
            session, alliance_id, player_name, name, screenshot_filename
        )

        if player is None:
            continue

        foundry_power = player_data.get("foundry_power", 0)
        voted = player_data.get("voted", False)

        # Add foundry signup
        result = add_foundry_signup(
            session,
            foundry_event_id=foundry_event.id,
            player_id=player.id,
            foundry_power=foundry_power,
            voted=voted,
            recorded_at=recorded_at,
        )
        if result is not None:
            signup_count += 1

    session.commit()
    logger.info(f"Saved foundry signups: {signup_count} signups for event {foundry_event.id}")

    return {
        "event_id": foundry_event.id,
        "signups": signup_count,
    }


def add_foundry_result(
    session: Session,
    foundry_event_id: int,
    player_id: int,
    score: int,
    rank: int | None,
    recorded_at: datetime,
) -> models.FoundryResult | None:
    """
    Add a foundry result record for a player.
    Skips if a record already exists for this player in this event.

    Args:
        session: Database session
        foundry_event_id: Foundry event ID
        player_id: Player ID
        score: Arsenal points score
        rank: Rank (1, 2, 3, etc.)
        recorded_at: When the screenshot was taken (UTC)

    Returns:
        FoundryResult model instance or None if already exists
    """
    # Check if record already exists
    stmt = select(models.FoundryResult).where(
        models.FoundryResult.foundry_event_id == foundry_event_id,
        models.FoundryResult.player_id == player_id,
    )
    existing = session.execute(stmt).scalar_one_or_none()

    if existing:
        logger.debug(f"Foundry result already exists for player {player_id} in event {foundry_event_id}")
        return None

    result = models.FoundryResult(
        foundry_event_id=foundry_event_id,
        player_id=player_id,
        score=score,
        rank=rank,
        recorded_at=recorded_at,
    )
    session.add(result)
    logger.debug(f"Added foundry result for player {player_id}: {score} (rank {rank})")
    return result


def save_foundry_result_ocr(
    session: Session,
    alliance_id: int,
    legion_number: int,
    event_date: datetime,
    players_data: list[dict[str, Any]],
    recorded_at: datetime,
    screenshot_filename: str | None = None,
) -> dict[str, int]:
    """
    Save foundry result OCR results to database.
    Finds foundry event and adds result records.

    Args:
        session: Database session
        alliance_id: Alliance ID
        legion_number: Legion number (1 or 2)
        event_date: When the foundry event occurs (UTC)
        players_data: List of player dicts with name, score, rank
        recorded_at: When the screenshot was taken (UTC)
        screenshot_filename: Optional filename of the screenshot for logging

    Returns:
        Dict with counts: {"event_id": N, "results": M}
    """
    # Find the foundry event (must exist from signup phase)
    stmt = select(models.FoundryEvent).where(
        models.FoundryEvent.alliance_id == alliance_id,
        models.FoundryEvent.legion_number == legion_number,
        models.FoundryEvent.event_date == event_date,
    )
    foundry_event = session.execute(stmt).scalar_one_or_none()

    if foundry_event is None:
        # Event doesn't exist yet, create it
        logger.warning(f"Foundry event not found for Legion {legion_number} on {event_date}, creating it")
        foundry_event = find_or_create_foundry_event(
            session,
            alliance_id=alliance_id,
            legion_number=legion_number,
            event_date=event_date,
        )

    result_count = 0

    for player_data in players_data:
        name = player_data.get("name")
        if not name:
            continue

        # Strip alliance tag for player matching
        player_name = name
        if player_name.startswith("[") and "]" in player_name:
            player_name = player_name.split("]", 1)[1].strip()

        # Find player in database (with fuzzy matching fallback)
        player = find_player_with_fuzzy_fallback(
            session, alliance_id, player_name, name, screenshot_filename
        )

        if player is None:
            continue

        score = player_data.get("score", 0)
        rank = player_data.get("rank")

        # Add foundry result
        result = add_foundry_result(
            session,
            foundry_event_id=foundry_event.id,
            player_id=player.id,
            score=score,
            rank=rank,
            recorded_at=recorded_at,
        )
        if result is not None:
            result_count += 1

    session.commit()
    logger.info(f"Saved foundry results: {result_count} results for event {foundry_event.id}")

    return {
        "event_id": foundry_event.id,
        "results": result_count,
    }
