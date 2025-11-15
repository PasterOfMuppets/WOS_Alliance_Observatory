#!/usr/bin/env python3
"""Test script for processing foundry signup screenshots."""
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
from observatory.db.foundry_operations import save_foundry_signup_ocr
from observatory.db.session import SessionLocal
from observatory.ocr.ai_client import OpenAIVisionExtractor
from observatory.ocr.timestamp_extractor import extract_timestamp
from observatory.settings import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Test foundry signup OCR with database persistence")
    parser.add_argument("image", type=Path, help="Path to foundry signup screenshot")
    parser.add_argument("--alliance-id", type=int, default=1, help="Alliance ID (default: 1)")
    parser.add_argument(
        "--event-date",
        type=str,
        required=True,
        help="Foundry event date in UTC (format: YYYY-MM-DD)",
    )
    parser.add_argument(
        "--legion",
        type=int,
        required=True,
        choices=[1, 2],
        help="Legion number (1 or 2)",
    )
    args = parser.parse_args()

    print(f"Processing foundry signup screenshot: {args.image}")
    print(f"Alliance ID: {args.alliance_id}")
    print(f"Legion: {args.legion}")
    print(f"Event date: {args.event_date} UTC")
    print()

    # Parse event date
    try:
        event_date = datetime.strptime(args.event_date, "%Y-%m-%d")
        event_date = pytz.UTC.localize(event_date)
    except ValueError as exc:
        print(f"Error parsing event date: {exc}")
        print("Format should be: YYYY-MM-DD (e.g., 2025-11-01)")
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
        signup_data = extractor.extract_foundry_signup(args.image)
    except Exception as exc:
        print(f"ERROR: AI OCR failed: {exc}")
        return

    print(f"\nExtracted signup data:")
    print(json.dumps(signup_data, indent=2))

    detected_legion = signup_data.get("legion_number")
    if detected_legion != args.legion:
        print(f"\nWARNING: Detected legion {detected_legion} doesn't match specified legion {args.legion}")
        print("Using specified legion number...")

    # Save to database
    print("\nSaving to database...")
    session = SessionLocal()
    try:
        result = save_foundry_signup_ocr(
            session=session,
            alliance_id=args.alliance_id,
            legion_number=args.legion,
            event_date=event_date,
            signup_data=signup_data,
            recorded_at=screenshot_recorded_at,
        )
        print(f"✓ Saved {result['signups']} signups to foundry event ID {result['event_id']}")

        # Query back to verify
        stmt = select(models.FoundryEvent).where(models.FoundryEvent.id == result['event_id'])
        event = session.execute(stmt).scalar_one()
        print(f"\nFoundry Event Details:")
        print(f"  ID: {event.id}")
        print(f"  Alliance: {event.alliance_id}")
        print(f"  Legion: {event.legion_number}")
        print(f"  Event Date: {event.event_date}")
        print(f"  Total Troop Power: {event.total_troop_power:,}" if event.total_troop_power else "  Total Troop Power: None")
        print(f"  Max Participants: {event.max_participants}")
        print(f"  Actual Participants: {event.actual_participants}")
        print(f"  Signups Recorded: {len(event.signups)}")

        # Show a few signups
        if event.signups:
            print(f"\nSample signups:")
            for signup in event.signups[:5]:
                print(f"  - {signup.player.name}: power={signup.foundry_power:,}, voted={signup.voted}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
