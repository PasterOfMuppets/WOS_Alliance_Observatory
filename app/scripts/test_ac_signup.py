#!/usr/bin/env python3
"""Test script for processing AC signup screenshots."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytz
from sqlalchemy import select

from observatory.db import models
from observatory.db.ac_operations import save_ac_signup_ocr
from observatory.db.session import SessionLocal
from observatory.ocr.ai_client import OpenAIVisionExtractor
from observatory.ocr.timestamp_extractor import extract_timestamp
from observatory.settings import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Test AC signup OCR with database persistence")
    parser.add_argument("image", type=Path, help="Path to AC signup screenshot")
    parser.add_argument("--alliance-id", type=int, default=1, help="Alliance ID (default: 1)")
    parser.add_argument(
        "--week-start",
        type=str,
        required=True,
        help="AC week start date (Monday) in UTC (format: YYYY-MM-DD)",
    )
    args = parser.parse_args()

    print(f"Processing AC signup screenshot: {args.image}")
    print(f"Alliance ID: {args.alliance_id}")
    print(f"Week start: {args.week_start} (Monday)")
    print()

    # Parse week start date
    try:
        week_start_date = datetime.strptime(args.week_start, "%Y-%m-%d")
        week_start_date = pytz.UTC.localize(week_start_date)
    except ValueError as exc:
        print(f"Error parsing week start date: {exc}")
        print("Format should be: YYYY-MM-DD (e.g., 2025-11-11)")
        return

    # Extract screenshot timestamp
    screenshot_recorded_at = extract_timestamp(args.image)
    if screenshot_recorded_at:
        print(f"Screenshot timestamp: {screenshot_recorded_at}")
    else:
        print("WARNING: Could not extract screenshot timestamp, using current time")
        screenshot_recorded_at = pytz.UTC.localize(datetime.utcnow())

    # Run AI OCR
    print("Running AI OCR extraction...")
    extractor = OpenAIVisionExtractor(model=settings.ai_ocr_model)
    try:
        signup_data = extractor.extract_ac_signup(args.image)
    except Exception as exc:
        print(f"ERROR: AI OCR failed: {exc}")
        return

    print(f"\nExtracted signup data:")
    print(f"  Total Registered: {signup_data.get('total_registered')}")
    print(f"  Total Power: {signup_data.get('total_power'):,}" if signup_data.get('total_power') else "  Total Power: None")
    print(f"  Players found: {len(signup_data.get('players', []))}")

    # Save to database
    print("\nSaving to database...")
    session = SessionLocal()
    try:
        result = save_ac_signup_ocr(
            session=session,
            alliance_id=args.alliance_id,
            week_start_date=week_start_date,
            signup_data=signup_data,
            recorded_at=screenshot_recorded_at,
        )
        print(f"✓ Saved {result['signups']} signups to AC event ID {result['event_id']}")

        # Query back to verify
        stmt = select(models.ACEvent).where(models.ACEvent.id == result['event_id'])
        event = session.execute(stmt).scalar_one()
        print(f"\nAC Event Details:")
        print(f"  ID: {event.id}")
        print(f"  Alliance: {event.alliance_id}")
        print(f"  Week Start: {event.week_start_date.date()}")
        print(f"  Total Registered: {event.total_registered}")
        print(f"  Total Power: {event.total_power:,}" if event.total_power else "  Total Power: None")
        print(f"  Signups Recorded: {len(event.signups)}")

        # Show a few signups
        if event.signups:
            print(f"\nSample signups (top 5 by power):")
            sorted_signups = sorted(event.signups, key=lambda s: s.ac_power, reverse=True)
            for signup in sorted_signups[:5]:
                print(f"  - {signup.player.name}: {signup.ac_power:,}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
