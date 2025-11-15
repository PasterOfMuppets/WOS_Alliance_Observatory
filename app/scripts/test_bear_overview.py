#!/usr/bin/env python3
"""Test script for processing bear event battle overview screenshots."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytesseract
from PIL import Image
from sqlalchemy import select

from observatory.db import models
from observatory.db.bear_operations import find_or_create_bear_event
from observatory.db.session import SessionLocal
from observatory.ocr.bear_overview_parser import parse_bear_overview

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_event_time(time_str: str) -> datetime:
    """Parse event time string to datetime (UTC)."""
    try:
        return datetime.strptime(time_str, "%Y%m%d%H%M")
    except ValueError:
        raise ValueError(
            "Invalid event time format. Expected: YYYYMMDDHHMM (UTC), "
            f"e.g., '202511120300' for 2025-11-12 03:00 UTC. Got: {time_str}"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Process bear event battle overview screenshot using Tesseract OCR"
    )
    parser.add_argument(
        "screenshot_path",
        help="Path to battle overview screenshot",
    )
    parser.add_argument(
        "--event-time",
        required=True,
        help="Bear trap start time in YYYYMMDDHHMM format (UTC), e.g., 202511120300",
    )
    parser.add_argument(
        "--alliance-id",
        type=int,
        default=1,
        help="Alliance ID (default: 1)",
    )

    args = parser.parse_args()

    # Parse event time
    started_at = parse_event_time(args.event_time)
    logger.info(f"Processing bear event for: {started_at} UTC")

    # Load screenshot
    screenshot_path = Path(args.screenshot_path)
    if not screenshot_path.exists():
        logger.error(f"Screenshot not found: {screenshot_path}")
        return

    logger.info(f"Loading screenshot: {screenshot_path}")
    image = Image.open(screenshot_path)

    # Extract text with Tesseract
    logger.info("Running Tesseract OCR...")
    text = pytesseract.image_to_string(image)
    logger.debug(f"OCR text:\n{text}")

    # Parse overview data
    logger.info("Parsing battle overview data...")
    overview_data = parse_bear_overview(text)

    trap_id = overview_data.get("trap_id")
    rally_count = overview_data.get("rally_count")
    total_damage = overview_data.get("total_damage")

    if trap_id is None:
        logger.error("Failed to extract trap ID from overview")
        return

    logger.info(f"Extracted data:")
    logger.info(f"  Trap ID: {trap_id}")
    logger.info(f"  Rally Count: {rally_count}")
    logger.info(f"  Total Damage: {total_damage:,}" if total_damage else "  Total Damage: None")

    # Extract event completion timestamp from image
    # The screenshot shows "2025-11-11 22:30:05" which is the ended_at time
    # We'll try to extract this from OCR text
    import re
    timestamp_pattern = r"(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})"
    timestamp_match = re.search(timestamp_pattern, text)
    ended_at = None
    if timestamp_match:
        year, month, day, hour, minute, second = map(int, timestamp_match.groups())
        ended_at = datetime(year, month, day, hour, minute, second)
        logger.info(f"  Event ended at: {ended_at} (extracted from screenshot)")

    # Save to database
    logger.info("Updating database...")
    session = SessionLocal()
    try:
        # Find or create bear event and update with overview stats
        bear_event = find_or_create_bear_event(
            session,
            alliance_id=args.alliance_id,
            trap_id=trap_id,
            started_at=started_at,
            ended_at=ended_at,
            rally_count=rally_count,
            total_damage=total_damage,
        )
        session.commit()

        logger.info(f"✓ Updated bear event ID: {bear_event.id}")
        logger.info(f"  Alliance ID: {bear_event.alliance_id}")
        logger.info(f"  Trap: {bear_event.trap_id}")
        logger.info(f"  Started: {bear_event.started_at}")
        logger.info(f"  Ended: {bear_event.ended_at}")
        logger.info(f"  Rallies: {bear_event.rally_count}")
        logger.info(f"  Total Damage: {bear_event.total_damage:,}" if bear_event.total_damage else "  Total Damage: None")

        # Query scores for this event
        stmt = select(models.BearScore).where(
            models.BearScore.bear_event_id == bear_event.id
        )
        scores = session.execute(stmt).scalars().all()
        logger.info(f"  Player Scores: {len(scores)}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
