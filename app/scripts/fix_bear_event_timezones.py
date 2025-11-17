#!/usr/bin/env python3
"""Convert all bear event timestamps to timezone-aware UTC."""
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
        print("Converting bear event timestamps to timezone-aware UTC...")
        print("=" * 60)

        # Check current state
        result = conn.execute(text("""
            SELECT COUNT(*) FROM bear_events
            WHERE started_at NOT LIKE '%+%' AND started_at NOT LIKE '%Z'
        """))
        naive_count = result.scalar()

        print(f"\nFound {naive_count} bear events with naive timestamps")

        if naive_count == 0:
            print("✓ All timestamps are already timezone-aware!")
            return

        # For SQLite, we need to append timezone info
        # Assuming all existing timestamps are UTC
        print("\nConverting timestamps to UTC format...")

        # Update started_at
        result = conn.execute(text("""
            UPDATE bear_events
            SET started_at = started_at || '+00:00'
            WHERE started_at NOT LIKE '%+%' AND started_at NOT LIKE '%Z'
        """))

        print(f"✓ Updated {result.rowcount} started_at timestamps")

        # Update ended_at (if not null)
        result = conn.execute(text("""
            UPDATE bear_events
            SET ended_at = ended_at || '+00:00'
            WHERE ended_at IS NOT NULL
            AND ended_at NOT LIKE '%+%' AND ended_at NOT LIKE '%Z'
        """))

        print(f"✓ Updated {result.rowcount} ended_at timestamps")

        # Verify
        result = conn.execute(text("""
            SELECT
                id,
                started_at,
                ended_at
            FROM bear_events
            ORDER BY id DESC
            LIMIT 5
        """))

        print("\n" + "=" * 60)
        print("Verification - Recent bear events:")
        print("=" * 60)

        for event in result.fetchall():
            print(f"\nEvent ID {event[0]}:")
            print(f"  started_at: {event[1]}")
            if event[2]:
                print(f"  ended_at: {event[2]}")

        print("\n✓ All bear event timestamps converted to timezone-aware UTC!")

if __name__ == "__main__":
    main()
