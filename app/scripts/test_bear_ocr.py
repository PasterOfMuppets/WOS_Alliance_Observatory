#!/usr/bin/env python3
"""Test bear event OCR pipeline with database persistence."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

import pytz

from observatory.db.bear_operations import save_bear_event_ocr
from observatory.db.session import SessionLocal
from observatory.ocr.ai_client import OpenAIVisionExtractor
from observatory.ocr.timestamp_extractor import extract_timestamp
from observatory.settings import settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Test bear event OCR with database persistence")
    parser.add_argument("image", type=Path, help="Path to bear event screenshot")
    parser.add_argument("--alliance-id", type=int, default=1, help="Alliance ID (default: 1)")
    parser.add_argument(
        "--event-time",
        type=str,
        required=True,
        help="Bear event start time in UTC (format: YYYY-MM-DD HH:MM)",
    )
    args = parser.parse_args()

    print(f"Processing bear event screenshot: {args.image}")
    print(f"Alliance ID: {args.alliance_id}")
    print(f"Event start time: {args.event_time} UTC")
    print()

    # Parse event start time
    try:
        event_started_at = datetime.strptime(args.event_time, "%Y-%m-%d %H:%M")
        event_started_at = pytz.UTC.localize(event_started_at)
    except ValueError as exc:
        print(f"Error parsing event time: {exc}")
        print("Format should be: YYYY-MM-DD HH:MM (e.g., 2025-11-11 14:20)")
        return

    # Extract screenshot timestamp
    screenshot_recorded_at = extract_timestamp(args.image)
    if screenshot_recorded_at:
        print(f"Screenshot timestamp: {screenshot_recorded_at}")
    else:
        print("WARNING: Could not extract screenshot timestamp, using current time")
        screenshot_recorded_at = datetime.now(pytz.UTC)
    print()

    # Run AI OCR
    print("Running AI OCR...")
    extractor = OpenAIVisionExtractor(model=settings.ai_ocr_model)
    bear_data = extractor.extract_bear_event(args.image)

    trap_id = bear_data.get("trap_id")
    players = bear_data.get("players", [])

    print(f"Trap ID: {trap_id}")
    print(f"Extracted {len(players)} player scores")
    print()

    # Display extracted data
    print("Extracted players:")
    print(json.dumps(players, indent=2, ensure_ascii=False))
    print()

    # Save to database
    print(f"Saving to database...")
    with SessionLocal() as session:
        result = save_bear_event_ocr(
            session=session,
            alliance_id=args.alliance_id,
            trap_id=trap_id,
            started_at=event_started_at,
            players_data=players,
            recorded_at=screenshot_recorded_at,
        )

    print(f"✓ Saved: Bear Event ID {result['event_id']}, {result['scores']} scores")
    print()

    # Query back to verify
    print("Querying bear event for verification...")
    with SessionLocal() as session:
        from observatory.db.models import BearEvent, BearScore
        from sqlalchemy import select, desc

        stmt = select(BearEvent).where(BearEvent.id == result['event_id'])
        event = session.execute(stmt).scalar_one()

        print(f"  Event: Trap {event.trap_id} started at {event.started_at}")

        scores_stmt = (
            select(BearScore)
            .where(BearScore.bear_event_id == event.id)
            .order_by(desc(BearScore.score))
            .limit(10)
        )
        scores = session.execute(scores_stmt).scalars().all()

        print(f"  Top {len(scores)} scores:")
        for score in scores:
            from observatory.db.models import Player
            player = session.execute(select(Player).where(Player.id == score.player_id)).scalar_one()
            rank_str = f"#{score.rank}" if score.rank else "Unranked"
            print(f"    {rank_str:10s} {player.name:30s} {score.score:,}")

    print()
    print("✓ Bear event test complete!")


if __name__ == "__main__":
    main()
