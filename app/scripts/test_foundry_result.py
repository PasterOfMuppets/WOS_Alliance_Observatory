#!/usr/bin/env python3
"""Test script for processing foundry result screenshots."""
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
from observatory.db.foundry_operations import save_foundry_result_ocr
from observatory.db.session import SessionLocal
from observatory.ocr.ai_client import OpenAIVisionExtractor
from observatory.ocr.timestamp_extractor import extract_timestamp
from observatory.settings import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Test foundry result OCR with database persistence")
    parser.add_argument("image", type=Path, help="Path to foundry result screenshot")
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

    print(f"Processing foundry result screenshot: {args.image}")
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
        result_data = extractor.extract_foundry_result(args.image)
    except Exception as exc:
        print(f"ERROR: AI OCR failed: {exc}")
        return

    print(f"\nExtracted result data:")
    print(json.dumps(result_data, indent=2))

    players_data = result_data.get("players", [])
    print(f"\nExtracted {len(players_data)} player results")

    # Save to database
    print("\nSaving to database...")
    session = SessionLocal()
    try:
        result = save_foundry_result_ocr(
            session=session,
            alliance_id=args.alliance_id,
            legion_number=args.legion,
            event_date=event_date,
            players_data=players_data,
            recorded_at=screenshot_recorded_at,
        )
        print(f"✓ Saved {result['results']} results to foundry event ID {result['event_id']}")

        # Query back to verify
        stmt = select(models.FoundryEvent).where(models.FoundryEvent.id == result['event_id'])
        event = session.execute(stmt).scalar_one()
        print(f"\nFoundry Event Details:")
        print(f"  ID: {event.id}")
        print(f"  Alliance: {event.alliance_id}")
        print(f"  Legion: {event.legion_number}")
        print(f"  Event Date: {event.event_date}")
        print(f"  Signups: {len(event.signups)}")
        print(f"  Results: {len(event.results)}")

        # Show top 5 results
        if event.results:
            print(f"\nTop 5 results:")
            sorted_results = sorted(event.results, key=lambda r: r.rank if r.rank else 999)
            for result_entry in sorted_results[:5]:
                print(f"  #{result_entry.rank}: {result_entry.player.name} - {result_entry.score:,}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
