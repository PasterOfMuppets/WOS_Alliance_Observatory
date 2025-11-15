"""Database operations for saving OCR results."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models
from .enums import PlayerStatus

logger = logging.getLogger(__name__)


def upsert_player(
    session: Session,
    alliance_id: int,
    name: str,
    power: int | None = None,
    furnace_level: str | None = None,
) -> models.Player:
    """
    Find or create a player by alliance_id and name.
    Updates current_power and current_furnace if provided.

    Args:
        session: Database session
        alliance_id: Alliance ID
        name: Player name
        power: Optional power value (integer, not millions)
        furnace_level: Optional furnace level (e.g., "FC4", "FC5", "25")

    Returns:
        Player model instance
    """
    # Try to find existing player
    stmt = select(models.Player).where(
        models.Player.alliance_id == alliance_id,
        models.Player.name == name
    )
    player = session.execute(stmt).scalar_one_or_none()

    if player is None:
        # Create new player
        player = models.Player(
            alliance_id=alliance_id,
            name=name,
            status=PlayerStatus.ACTIVE,
            current_power=power,
            current_furnace=_parse_furnace_level(furnace_level),
        )
        session.add(player)
        session.flush()  # Ensure player.id is available
        logger.info(f"Created new player: {name} in alliance {alliance_id}")
    else:
        # Update current values (don't flush to avoid cascade issues)
        if power is not None:
            player.current_power = power
        if furnace_level is not None:
            player.current_furnace = _parse_furnace_level(furnace_level)
        logger.debug(f"Updated player: {name}")

    return player


def add_power_history(
    session: Session,
    player_id: int,
    power: int,
    captured_at: datetime,
) -> models.PlayerPowerHistory:
    """
    Add a power history record for a player.

    Args:
        session: Database session
        player_id: Player ID
        power: Power value (integer, not millions)
        captured_at: When the screenshot was taken (in UTC)

    Returns:
        PlayerPowerHistory model instance
    """
    history = models.PlayerPowerHistory(
        player_id=player_id,
        power=power,
        captured_at=captured_at,
    )
    session.add(history)
    logger.debug(f"Added power history for player {player_id}: {power} at {captured_at}")
    return history


def add_furnace_history(
    session: Session,
    player_id: int,
    furnace_level: str,
    captured_at: datetime,
) -> models.PlayerFurnaceHistory:
    """
    Add a furnace history record for a player.

    Args:
        session: Database session
        player_id: Player ID
        furnace_level: Furnace level string (e.g., "FC4", "FC5", "25")
        captured_at: When the screenshot was taken (in UTC)

    Returns:
        PlayerFurnaceHistory model instance
    """
    furnace_int = _parse_furnace_level(furnace_level)
    history = models.PlayerFurnaceHistory(
        player_id=player_id,
        furnace_level=furnace_int,
        captured_at=captured_at,
    )
    session.add(history)
    logger.debug(f"Added furnace history for player {player_id}: {furnace_level} at {captured_at}")
    return history


def save_alliance_members_ocr(
    session: Session,
    alliance_id: int,
    players_data: list[dict[str, Any]],
    captured_at: datetime,
) -> dict[str, int]:
    """
    Save alliance members OCR results to database.
    Creates/updates players and adds history records.

    Args:
        session: Database session
        alliance_id: Alliance ID
        players_data: List of player dicts with name, power, furnace_level
        captured_at: When the screenshot was taken (in UTC)

    Returns:
        Dict with counts: {"players": N, "power_records": M, "furnace_records": K}
    """
    player_count = 0
    power_count = 0
    furnace_count = 0

    for player_data in players_data:
        name = player_data.get("name")
        if not name or name.lower() == "null":
            continue

        # Handle both "power" (integer) and "power_millions" (float) formats
        power = player_data.get("power")
        if power is None and "power_millions" in player_data:
            power_millions = player_data.get("power_millions")
            if power_millions is not None:
                power = int(float(power_millions) * 1_000_000)

        furnace_level = player_data.get("furnace_level")

        # Upsert player
        player = upsert_player(
            session,
            alliance_id=alliance_id,
            name=name,
            power=power,
            furnace_level=furnace_level,
        )
        player_count += 1

        # Add power history if available
        if power is not None:
            add_power_history(session, player.id, power, captured_at)
            power_count += 1

        # Add furnace history if available
        if furnace_level is not None:
            add_furnace_history(session, player.id, furnace_level, captured_at)
            furnace_count += 1

    session.commit()
    logger.info(
        f"Saved alliance members: {player_count} players, "
        f"{power_count} power records, {furnace_count} furnace records"
    )

    return {
        "players": player_count,
        "power_records": power_count,
        "furnace_records": furnace_count,
    }


def _parse_furnace_level(furnace_str: str | None) -> int | None:
    """
    Parse furnace level string to integer.

    Examples:
        "FC4" -> 4
        "FC5" -> 5
        "25" -> 25
        "3" -> 3

    Args:
        furnace_str: Furnace level string

    Returns:
        Integer furnace level or None if invalid
    """
    if furnace_str is None:
        return None

    furnace_str = str(furnace_str).strip().upper()

    # Handle "FC" prefix
    if furnace_str.startswith("FC"):
        furnace_str = furnace_str[2:]

    try:
        return int(furnace_str)
    except (ValueError, TypeError):
        logger.warning(f"Could not parse furnace level: {furnace_str}")
        return None
