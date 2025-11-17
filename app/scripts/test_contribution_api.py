#!/usr/bin/env python3
"""Test the contribution API endpoint logic."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from observatory.settings import Settings
from observatory.db import models

def main():
    settings = Settings()
    engine = create_engine(settings.database_url)

    with Session(engine) as session:
        alliance_id = 1  # Test Alliance

        print("=" * 80)
        print("TESTING API QUERY LOGIC")
        print("=" * 80)

        # Get unique weeks (this is what the API does)
        stmt = select(models.ContributionSnapshot.week_start_date).where(
            models.ContributionSnapshot.alliance_id == alliance_id
        ).distinct().order_by(models.ContributionSnapshot.week_start_date.desc())

        weeks = session.execute(stmt).scalars().all()

        print(f"\nFound {len(weeks)} unique weeks")
        print(f"Weeks: {weeks}")

        if len(weeks) == 0:
            print("\n⚠️  NO WEEKS FOUND! This is why the frontend shows nothing.")
            print("\nDebugging: Let's check the raw data...")

            # Check raw data
            stmt = select(models.ContributionSnapshot).where(
                models.ContributionSnapshot.alliance_id == alliance_id
            ).limit(5)
            snapshots = session.execute(stmt).scalars().all()

            print(f"\nFound {len(snapshots)} snapshots in database")
            for s in snapshots:
                print(f"  Week start: {s.week_start_date} (type: {type(s.week_start_date)})")
                print(f"  Snapshot date: {s.snapshot_date}")

            return

        # Build the response like the API does
        result = {
            "weeks": []
        }

        for w in weeks:
            print(f"\nProcessing week: {w} (type: {type(w)})")

            # Get snapshots for this week
            stmt = select(models.ContributionSnapshot).where(
                models.ContributionSnapshot.alliance_id == alliance_id,
                models.ContributionSnapshot.week_start_date == w
            ).order_by(models.ContributionSnapshot.rank)

            snapshots = session.execute(stmt).scalars().all()
            print(f"  Found {len(snapshots)} snapshots for this week")

            week_data = {
                "week_start": w.isoformat(),
                "snapshots": [
                    {
                        "snapshot_date": s.snapshot_date.isoformat(),
                        "player_name": s.player.name,
                        "contribution": s.contribution_amount,
                        "rank": s.rank
                    }
                    for s in snapshots
                ]
            }

            result["weeks"].append(week_data)

        print("\n" + "=" * 80)
        print("API RESPONSE STRUCTURE")
        print("=" * 80)
        print(f"\nTotal weeks in response: {len(result['weeks'])}")

        for i, week in enumerate(result["weeks"]):
            print(f"\nWeek {i + 1}:")
            print(f"  week_start: {week['week_start']}")
            print(f"  snapshots: {len(week['snapshots'])} players")
            if week['snapshots']:
                print(f"  First player: {week['snapshots'][0]['player_name']} - {week['snapshots'][0]['contribution']}")

        if len(result["weeks"]) > 0:
            print("\n✓ API should be returning data!")
        else:
            print("\n✗ API would return empty weeks array")


if __name__ == "__main__":
    main()
