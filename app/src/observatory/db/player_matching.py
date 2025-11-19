"""Player name fuzzy matching utilities for OCR results."""
from __future__ import annotations

import difflib
import logging
from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session
    from . import models

logger = logging.getLogger(__name__)

# Fuzzy match threshold (0.0-1.0, higher = stricter)
FUZZY_MATCH_THRESHOLD = 0.85


def fuzzy_match_player(
    session: Session,
    alliance_id: int,
    player_name: str,
    threshold: float = FUZZY_MATCH_THRESHOLD
) -> tuple[models.Player | None, float]:
    """
    Attempt to find a player using fuzzy name matching.

    This function is used to recover from OCR misreads by finding the closest
    matching player name in the database. It uses Python's difflib for similarity scoring.

    Args:
        session: Database session
        alliance_id: Alliance ID to search within
        player_name: The OCR-extracted player name to match
        threshold: Minimum similarity score (0.0-1.0) to accept a match

    Returns:
        Tuple of (matched_player, similarity_score) or (None, 0.0) if no match found

    Example:
        OCR reads "Valor1n" but database has "Valorin" -> returns (Player, 0.93)
    """
    from . import models

    # Get all player names for this alliance
    stmt = select(models.Player).where(models.Player.alliance_id == alliance_id)
    all_players = session.execute(stmt).scalars().all()

    if not all_players:
        return (None, 0.0)

    # Build list of (player, name) tuples
    player_names = [(p, p.name) for p in all_players]

    # Find close matches using difflib
    names_only = [name for _, name in player_names]
    matches = difflib.get_close_matches(player_name, names_only, n=1, cutoff=threshold)

    if not matches:
        return (None, 0.0)

    # Get the best match
    best_match_name = matches[0]

    # Calculate exact similarity score
    similarity = difflib.SequenceMatcher(None, player_name.lower(), best_match_name.lower()).ratio()

    # Find the player object
    matched_player = next((p for p, name in player_names if name == best_match_name), None)

    return (matched_player, similarity)


def find_player_with_fuzzy_fallback(
    session: Session,
    alliance_id: int,
    player_name: str,
    original_ocr_text: str,
    screenshot_filename: str | None = None
) -> models.Player | None:
    """
    Find a player by exact match, falling back to fuzzy matching if not found.

    Logs the matching process for audit purposes:
    - Info log when fuzzy match succeeds (shows OCR text → matched name)
    - Warning log when no match found (exact or fuzzy)

    Args:
        session: Database session
        alliance_id: Alliance ID to search within
        player_name: Cleaned player name (alliance tag stripped)
        original_ocr_text: Original OCR text before cleaning (for logging)
        screenshot_filename: Optional screenshot filename for logging context

    Returns:
        Player model if found (exact or fuzzy), None otherwise
    """
    from . import models

    # Try exact match first
    stmt = select(models.Player).where(
        models.Player.alliance_id == alliance_id,
        models.Player.name == player_name
    )
    player = session.execute(stmt).scalar_one_or_none()

    if player is not None:
        return player

    # Exact match failed, try fuzzy matching
    fuzzy_player, similarity = fuzzy_match_player(session, alliance_id, player_name)

    if fuzzy_player is not None:
        source_info = f" in {screenshot_filename}" if screenshot_filename else ""
        logger.info(
            f"Fuzzy matched player: '{player_name}' (from {original_ocr_text}) → '{fuzzy_player.name}' "
            f"(similarity: {similarity:.2%}){source_info}"
        )
        return fuzzy_player

    # No match found (exact or fuzzy)
    source_info = f" in {screenshot_filename}" if screenshot_filename else ""
    logger.warning(f"Player not found: {player_name} (from {original_ocr_text}){source_info}")

    return None
