#!/usr/bin/env python3
"""Check and fix duplicate contribution snapshots."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine, text
from observatory.settings import Settings

def main():
    settings = Settings()
    engine = create_engine(settings.database_url)

    with engine.begin() as conn:
        print("=" * 60)
        print("STEP 1: Checking for duplicates...")
        print("=" * 60)

        result = conn.execute(text("""
            SELECT
                alliance_id,
                player_id,
                week_start_date,
                snapshot_date,
                COUNT(*) as duplicate_count
            FROM contribution_snapshots
            GROUP BY alliance_id, player_id, week_start_date, snapshot_date
            HAVING COUNT(*) > 1
            ORDER BY duplicate_count DESC
            LIMIT 20
        """))

        duplicates = result.fetchall()

        if not duplicates:
            print("✓ No duplicates found!")
        else:
            print(f"✗ Found {len(duplicates)} sets of duplicates:")
            for row in duplicates:
                print(f"  Alliance {row[0]}, Player {row[1]}, Week {row[2]}, Snapshot {row[3]}: {row[4]} copies")

        print("\n" + "=" * 60)
        print("STEP 2: Normalizing dates to midnight UTC...")
        print("=" * 60)

        result = conn.execute(text("""
            UPDATE contribution_snapshots
            SET snapshot_date = datetime(date(snapshot_date)),
                week_start_date = datetime(date(week_start_date))
        """))

        print(f"✓ Normalized {result.rowcount} rows")

        print("\n" + "=" * 60)
        print("STEP 3: Removing duplicates (keeping earliest)...")
        print("=" * 60)

        result = conn.execute(text("""
            DELETE FROM contribution_snapshots
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM contribution_snapshots
                GROUP BY alliance_id, player_id, week_start_date, snapshot_date
            )
        """))

        print(f"✓ Deleted {result.rowcount} duplicate rows")

        print("\n" + "=" * 60)
        print("STEP 4: Verifying fix...")
        print("=" * 60)

        result = conn.execute(text("""
            SELECT
                alliance_id,
                player_id,
                week_start_date,
                snapshot_date,
                COUNT(*) as duplicate_count
            FROM contribution_snapshots
            GROUP BY alliance_id, player_id, week_start_date, snapshot_date
            HAVING COUNT(*) > 1
        """))

        remaining = result.fetchall()

        if not remaining:
            print("✓ All duplicates removed successfully!")
        else:
            print(f"✗ Warning: {len(remaining)} sets of duplicates still remain")

        print("\n" + "=" * 60)
        print("DONE!")
        print("=" * 60)

if __name__ == "__main__":
    main()
