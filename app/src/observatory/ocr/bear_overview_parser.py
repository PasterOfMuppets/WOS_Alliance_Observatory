"""Parser for bear event battle overview screenshots (Tesseract-based)."""
from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def parse_bear_overview(text: str) -> dict[str, Any]:
    """
    Parse bear event battle overview text extracted by Tesseract.

    Extracts:
    - trap_id: 1 or 2 (from "[Hunting Trap 1]" or "[Hunting Trap 2]")
    - rally_count: integer (from "Rallies: 50")
    - total_damage: integer (from "Total Alliance Damage: 57,815,870,631")

    Args:
        text: Raw OCR text from Tesseract

    Returns:
        Dict with trap_id, rally_count, total_damage (or None if not found)
    """
    result: dict[str, Any] = {
        "trap_id": None,
        "rally_count": None,
        "total_damage": None,
    }

    # Extract trap ID from "[Hunting Trap 1]" or "[Hunting Trap 2]"
    trap_pattern = r"\[Hunting\s+Trap\s+(\d+)\]"
    trap_match = re.search(trap_pattern, text, re.IGNORECASE)
    if trap_match:
        result["trap_id"] = int(trap_match.group(1))
        logger.debug(f"Found trap_id: {result['trap_id']}")
    else:
        logger.warning("Could not find trap ID in text")

    # Extract rally count from "Rallies: 50"
    rally_pattern = r"Rallies:\s*(\d+)"
    rally_match = re.search(rally_pattern, text, re.IGNORECASE)
    if rally_match:
        result["rally_count"] = int(rally_match.group(1))
        logger.debug(f"Found rally_count: {result['rally_count']}")
    else:
        logger.warning("Could not find rally count in text")

    # Extract total damage from "Total Alliance Damage: 57,815,870,631"
    # Handle both formats: with commas and without
    damage_pattern = r"Total\s+Alliance\s+Damage:\s*([\d,]+)"
    damage_match = re.search(damage_pattern, text, re.IGNORECASE)
    if damage_match:
        damage_str = damage_match.group(1).replace(",", "")
        try:
            result["total_damage"] = int(damage_str)
            logger.debug(f"Found total_damage: {result['total_damage']}")
        except ValueError:
            logger.warning(f"Could not parse damage value: {damage_match.group(1)}")
    else:
        logger.warning("Could not find total alliance damage in text")

    return result
