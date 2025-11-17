#!/usr/bin/env python3
"""Check for duplicate bear events."""
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
        print("Checking for duplicate bear events...")
        print("=" * 60)

        # Find bear events with the same started_at timestamp
        result = conn.execute(text("""
            SELECT
                alliance_id,
                trap_id,
                started_at,
                COUNT(*) as event_count
            FROM bear_events
            GROUP BY alliance_id, trap_id, started_at
            HAVING COUNT(*) > 1
            ORDER BY event_count DESC, started_at DESC
            LIMIT 20
        """))

        duplicates = result.fetchall()

        if not duplicates:
            print("✓ No duplicate bear events found!")
        else:
            print(f"✗ Found {len(duplicates)} sets of duplicate bear events:\n")
            for row in duplicates:
                print(f"  Alliance {row[0]}, Trap {row[1]}, Started {row[2]}: {row[3]} duplicate events")

        print("\n" + "=" * 60)
        print("All bear events (most recent 20):")
        print("=" * 60)

        result = conn.execute(text("""
            SELECT
                id,
                alliance_id,
                trap_id,
                started_at,
                ended_at,
                (SELECT COUNT(*) FROM bear_scores WHERE bear_event_id = bear_events.id) as score_count
            FROM bear_events
            ORDER BY started_at DESC
            LIMIT 20
        """))

        events = result.fetchall()
        for event in events:
            print(f"  ID {event[0]}: Trap {event[2]}, Started {event[3]}, {event[5]} scores")

if __name__ == "__main__":
    main()
