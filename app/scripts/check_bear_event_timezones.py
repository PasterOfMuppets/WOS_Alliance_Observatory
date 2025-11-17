#!/usr/bin/env python3
"""Check if bear events have timezone-aware timestamps."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine, text
from observatory.settings import Settings

def main():
    settings = Settings()
    engine = create_engine(settings.database_url)

    with engine.connect() as conn:
        print("=" * 60)
        print("Checking bear event timestamps for timezone info...")
        print("=" * 60)

        result = conn.execute(text("""
            SELECT
                id,
                trap_id,
                started_at,
                typeof(started_at) as type
            FROM bear_events
            ORDER BY id DESC
            LIMIT 10
        """))

        events = result.fetchall()

        if not events:
            print("No bear events found")
            return

        for event in events:
            print(f"\nEvent ID {event[0]}, Trap {event[1]}:")
            print(f"  started_at: {event[2]}")
            print(f"  SQLite type: {event[3]}")

            # Check if it contains timezone info
            if '+' in str(event[2]) or 'Z' in str(event[2]):
                print(f"  ✓ Has timezone info")
            else:
                print(f"  ✗ Missing timezone info (naive datetime)")

if __name__ == "__main__":
    main()
