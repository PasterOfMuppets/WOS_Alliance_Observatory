#!/usr/bin/env python3
"""Test the full OCR pipeline with database persistence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from observatory.db.operations import save_alliance_members_ocr
from observatory.db.session import SessionLocal
from observatory.ocr.ai_client import OpenAIVisionExtractor
from observatory.ocr.timestamp_extractor import extract_timestamp
from observatory.settings import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Test OCR pipeline with database persistence")
    parser.add_argument("image", type=Path, help="Path to screenshot image")
    parser.add_argument("--alliance-id", type=int, default=1, help="Alliance ID (default: 1)")
    args = parser.parse_args()

    print(f"Processing: {args.image}")
    print(f"AI OCR enabled: {settings.ai_ocr_enabled}")
    print(f"Model: {settings.ai_ocr_model}")
    print(f"Timezone: {settings.screenshot_timezone}")
    print()

    # Extract timestamp from screenshot
    captured_at = extract_timestamp(args.image)
    if captured_at:
        print(f"Screenshot timestamp: {captured_at} UTC")
    else:
        print("WARNING: Could not extract timestamp, using current time")
        from datetime import datetime
        import pytz
        captured_at = datetime.now(pytz.UTC)
    print()

    # Run AI OCR
    print("Running AI OCR...")
    extractor = OpenAIVisionExtractor(model=settings.ai_ocr_model)
    players = extractor.extract_players(args.image)
    print(f"Extracted {len(players)} players")
    print()

    # Display extracted data
    print("Extracted players:")
    print(json.dumps(players, indent=2, ensure_ascii=False))
    print()

    # Save to database
    print(f"Saving to database (alliance_id={args.alliance_id})...")
    with SessionLocal() as session:
        result = save_alliance_members_ocr(
            session=session,
            alliance_id=args.alliance_id,
            players_data=players,
            captured_at=captured_at,
        )

    print(f"✓ Saved: {result['players']} players, {result['power_records']} power records, {result['furnace_records']} furnace records")
    print()

    # Query back to verify
    print("Querying power history for verification...")
    with SessionLocal() as session:
        from observatory.db.models import Player, PlayerPowerHistory
        from sqlalchemy import select, desc

        stmt = select(Player).where(Player.alliance_id == args.alliance_id).limit(5)
        sample_players = session.execute(stmt).scalars().all()

        for player in sample_players:
            history_stmt = (
                select(PlayerPowerHistory)
                .where(PlayerPowerHistory.player_id == player.id)
                .order_by(desc(PlayerPowerHistory.captured_at))
                .limit(3)
            )
            history = session.execute(history_stmt).scalars().all()
            print(f"  {player.name}: {len(history)} power records")
            for record in history:
                print(f"    - {record.power:,} at {record.captured_at} (saved at {record.created_at})")

    print()
    print("✓ Pipeline test complete!")


if __name__ == "__main__":
    main()
