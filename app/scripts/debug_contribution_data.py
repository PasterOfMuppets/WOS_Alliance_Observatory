#!/usr/bin/env python3
"""Debug contribution snapshot data in the database."""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine, text
from observatory.settings import Settings

def main():
    settings = Settings()
    engine = create_engine(settings.database_url)

    with engine.connect() as conn:
        print("=" * 80)
        print("CONTRIBUTION SNAPSHOTS SUMMARY")
        print("=" * 80)

        # Check total count
        result = conn.execute(text("SELECT COUNT(*) FROM contribution_snapshots"))
        total = result.scalar()
        print(f"\nTotal contribution snapshots: {total}")

        if total == 0:
            print("\n⚠️  NO DATA FOUND IN contribution_snapshots TABLE!")
            print("\nPossible reasons:")
            print("1. Data was deleted by migration")
            print("2. No contribution screenshots have been processed yet")
            print("3. Screenshots were processed but failed to save")

            # Check if there are any processed screenshots
            result = conn.execute(text("""
                SELECT COUNT(*)
                FROM screenshots
                WHERE detected_type = 'CONTRIBUTION' AND status = 'PROCESSED'
            """))
            processed_count = result.scalar()
            print(f"\nProcessed CONTRIBUTION screenshots: {processed_count}")

            return

        # Check by alliance
        print("\n" + "=" * 80)
        print("SNAPSHOTS BY ALLIANCE")
        print("=" * 80)
        result = conn.execute(text("""
            SELECT
                a.name as alliance_name,
                a.id as alliance_id,
                COUNT(*) as snapshot_count
            FROM contribution_snapshots cs
            JOIN alliances a ON cs.alliance_id = a.id
            GROUP BY a.id, a.name
        """))

        for row in result:
            print(f"\nAlliance: {row[0]} (ID: {row[1]})")
            print(f"  Total snapshots: {row[2]}")

        # Check by week
        print("\n" + "=" * 80)
        print("SNAPSHOTS BY WEEK")
        print("=" * 80)
        result = conn.execute(text("""
            SELECT
                week_start_date,
                COUNT(DISTINCT snapshot_date) as num_snapshots,
                COUNT(*) as total_records,
                MIN(snapshot_date) as first_snapshot,
                MAX(snapshot_date) as last_snapshot
            FROM contribution_snapshots
            GROUP BY week_start_date
            ORDER BY week_start_date DESC
        """))

        rows = list(result)
        if rows:
            for row in rows:
                print(f"\nWeek starting {row[0]}:")
                print(f"  Snapshot dates: {row[1]}")
                print(f"  Total records: {row[2]}")
                print(f"  First snapshot: {row[3]}")
                print(f"  Last snapshot: {row[4]}")
        else:
            print("\nNo data grouped by weeks")

        # Check for data from each snapshot date
        print("\n" + "=" * 80)
        print("RECENT SNAPSHOT DATES")
        print("=" * 80)
        result = conn.execute(text("""
            SELECT
                snapshot_date,
                COUNT(DISTINCT player_id) as num_players,
                COUNT(*) as num_records
            FROM contribution_snapshots
            GROUP BY snapshot_date
            ORDER BY snapshot_date DESC
            LIMIT 10
        """))

        for row in result:
            print(f"  {row[0]}: {row[1]} players ({row[2]} records)")

        # Check for duplicates that might still exist
        print("\n" + "=" * 80)
        print("CHECKING FOR DUPLICATES")
        print("=" * 80)
        result = conn.execute(text("""
            SELECT
                alliance_id,
                player_id,
                week_start_date,
                snapshot_date,
                COUNT(*) as count
            FROM contribution_snapshots
            GROUP BY alliance_id, player_id, week_start_date, snapshot_date
            HAVING COUNT(*) > 1
            LIMIT 10
        """))

        dup_rows = list(result)
        if dup_rows:
            print(f"\n⚠️  Found {len(dup_rows)} duplicate combinations:")
            for row in dup_rows:
                print(f"  Alliance {row[0]}, Player {row[1]}, Week {row[2]}, Snapshot {row[3]}: {row[4]} records")
        else:
            print("\n✓ No duplicates found!")

        # Sample some actual data
        print("\n" + "=" * 80)
        print("SAMPLE DATA (5 most recent records)")
        print("=" * 80)
        result = conn.execute(text("""
            SELECT
                cs.id,
                p.name as player_name,
                cs.contribution_amount,
                cs.rank,
                cs.week_start_date,
                cs.snapshot_date,
                cs.created_at
            FROM contribution_snapshots cs
            JOIN players p ON cs.player_id = p.id
            ORDER BY cs.created_at DESC
            LIMIT 5
        """))

        for row in result:
            print(f"\nID: {row[0]}")
            print(f"  Player: {row[1]}")
            print(f"  Contribution: {row[2]}")
            print(f"  Rank: {row[3]}")
            print(f"  Week start: {row[4]}")
            print(f"  Snapshot date: {row[5]}")
            print(f"  Created: {row[6]}")


if __name__ == "__main__":
    main()
