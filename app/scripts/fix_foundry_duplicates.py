#!/usr/bin/env python3
"""Manually fix foundry duplicates and add unique constraints."""

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
        print("STEP 1: Removing duplicate foundry signups")
        print("=" * 80)

        # Delete duplicate foundry_signups, keeping the earliest (MIN id)
        result = conn.execute(text("""
            DELETE FROM foundry_signups
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM foundry_signups
                GROUP BY foundry_event_id, player_id
            )
        """))
        print(f"Deleted {result.rowcount} duplicate signup records")
        conn.commit()

        print()
        print("=" * 80)
        print("STEP 2: Removing duplicate foundry results")
        print("=" * 80)

        # Delete duplicate foundry_results, keeping the earliest (MIN id)
        result = conn.execute(text("""
            DELETE FROM foundry_results
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM foundry_results
                GROUP BY foundry_event_id, player_id
            )
        """))
        print(f"Deleted {result.rowcount} duplicate result records")
        conn.commit()

        print()
        print("=" * 80)
        print("STEP 3: Creating unique index on foundry_signups")
        print("=" * 80)

        try:
            conn.execute(text("""
                CREATE UNIQUE INDEX uq_foundry_signup_event_player
                ON foundry_signups(foundry_event_id, player_id)
            """))
            print("✓ Created unique index on foundry_signups")
            conn.commit()
        except Exception as e:
            if "already exists" in str(e) or "UNIQUE constraint" in str(e):
                print("✓ Unique index already exists on foundry_signups")
            else:
                print(f"✗ Error creating index: {e}")
                raise

        print()
        print("=" * 80)
        print("STEP 4: Creating unique index on foundry_results")
        print("=" * 80)

        try:
            conn.execute(text("""
                CREATE UNIQUE INDEX uq_foundry_result_event_player
                ON foundry_results(foundry_event_id, player_id)
            """))
            print("✓ Created unique index on foundry_results")
            conn.commit()
        except Exception as e:
            if "already exists" in str(e) or "UNIQUE constraint" in str(e):
                print("✓ Unique index already exists on foundry_results")
            else:
                print(f"✗ Error creating index: {e}")
                raise

        print()
        print("=" * 80)
        print("STEP 5: Verifying no duplicates remain")
        print("=" * 80)

        result = conn.execute(text("""
            SELECT COUNT(*) as count
            FROM (
                SELECT foundry_event_id, player_id, COUNT(*) as cnt
                FROM foundry_signups
                GROUP BY foundry_event_id, player_id
                HAVING COUNT(*) > 1
            )
        """))
        signup_dups = result.scalar()

        result = conn.execute(text("""
            SELECT COUNT(*) as count
            FROM (
                SELECT foundry_event_id, player_id, COUNT(*) as cnt
                FROM foundry_results
                GROUP BY foundry_event_id, player_id
                HAVING COUNT(*) > 1
            )
        """))
        result_dups = result.scalar()

        if signup_dups == 0 and result_dups == 0:
            print("✓ No duplicates found!")
            print("\n🎉 All done! Duplicates removed and unique constraints added.")
        else:
            print(f"✗ Still found {signup_dups} duplicate signups and {result_dups} duplicate results")
            sys.exit(1)

if __name__ == "__main__":
    main()
