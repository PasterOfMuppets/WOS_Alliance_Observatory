#!/usr/bin/env python3
"""Merge duplicate bear events that occurred on the same day."""
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine, text
from observatory.settings import Settings

def main():
    settings = Settings()
    engine = create_engine(settings.database_url)

    with engine.begin() as conn:
        print("=" * 60)
        print("Finding bear events to merge...")
        print("=" * 60)

        # Find groups of events within 24 hours of each other for the same trap
        result = conn.execute(text("""
            SELECT
                id,
                alliance_id,
                trap_id,
                started_at,
                ended_at,
                rally_count,
                total_damage,
                DATE(started_at) as event_date
            FROM bear_events
            ORDER BY alliance_id, trap_id, started_at
        """))

        events = result.fetchall()

        # Group events by alliance, trap, and date
        event_groups = {}
        for event in events:
            key = (event[1], event[2], event[7])  # alliance_id, trap_id, event_date
            if key not in event_groups:
                event_groups[key] = []
            event_groups[key].append(event)

        total_merged = 0

        for key, group in event_groups.items():
            if len(group) <= 1:
                continue

            alliance_id, trap_id, event_date = key
            print(f"\nFound {len(group)} events for Trap {trap_id} on {event_date}:")

            # Keep the first event, merge others into it
            primary_event = group[0]
            events_to_merge = group[1:]

            print(f"  Primary event: ID {primary_event[0]} at {primary_event[3]}")

            for dup_event in events_to_merge:
                print(f"  Merging event: ID {dup_event[0]} at {dup_event[3]}")

                # Move all scores from duplicate event to primary event
                result = conn.execute(text("""
                    UPDATE bear_scores
                    SET bear_event_id = :primary_id
                    WHERE bear_event_id = :dup_id
                    AND player_id NOT IN (
                        SELECT player_id FROM bear_scores WHERE bear_event_id = :primary_id
                    )
                """), {"primary_id": primary_event[0], "dup_id": dup_event[0]})

                moved_scores = result.rowcount
                if moved_scores > 0:
                    print(f"    Moved {moved_scores} unique scores")

                # Delete duplicate scores (same player in both events)
                result = conn.execute(text("""
                    DELETE FROM bear_scores
                    WHERE bear_event_id = :dup_id
                """), {"dup_id": dup_event[0]})

                deleted_scores = result.rowcount
                if deleted_scores > 0:
                    print(f"    Deleted {deleted_scores} duplicate scores")

                # Delete the duplicate event
                conn.execute(text("""
                    DELETE FROM bear_events WHERE id = :dup_id
                """), {"dup_id": dup_event[0]})

                total_merged += 1

        print("\n" + "=" * 60)
        print(f"✓ Merged {total_merged} duplicate bear events")
        print("=" * 60)

        # Show remaining events
        print("\nRemaining bear events:")
        result = conn.execute(text("""
            SELECT
                id,
                alliance_id,
                trap_id,
                started_at,
                (SELECT COUNT(*) FROM bear_scores WHERE bear_event_id = bear_events.id) as score_count
            FROM bear_events
            ORDER BY started_at DESC
            LIMIT 20
        """))

        events = result.fetchall()
        for event in events:
            print(f"  ID {event[0]}: Trap {event[2]}, Started {event[3]}, {event[4]} scores")

if __name__ == "__main__":
    main()
