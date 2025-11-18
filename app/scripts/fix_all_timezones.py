#!/usr/bin/env python3
"""Convert ALL naive timestamps in the database to timezone-aware UTC."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine, text
from observatory.settings import Settings

def main():
    settings = Settings()
    engine = create_engine(settings.database_url)

    # All tables and datetime columns that need fixing
    tables_to_fix = [
        ('players', ['created_at', 'updated_at']),
        ('player_power_history', ['captured_at', 'created_at']),
        ('player_furnace_history', ['captured_at', 'created_at']),
        ('contribution_snapshots', ['week_start_date', 'snapshot_date', 'recorded_at', 'created_at']),
        ('foundry_events', ['event_date', 'created_at']),
        ('foundry_signups', ['recorded_at', 'created_at']),
        ('foundry_results', ['recorded_at', 'created_at']),
        ('ac_events', ['week_start_date', 'created_at']),
        ('ac_signups', ['recorded_at', 'created_at']),
        ('screenshots', ['created_at', 'processed_at']),
        ('event_stats', ['captured_at']),
    ]

    with engine.begin() as conn:
        print("=" * 60)
        print("Converting ALL timestamps to timezone-aware UTC...")
        print("=" * 60)

        total_updated = 0

        for table, columns in tables_to_fix:
            print(f"\nProcessing table: {table}")

            for col in columns:
                result = conn.execute(text(f"""
                    UPDATE {table}
                    SET {col} = {col} || '+00:00'
                    WHERE {col} IS NOT NULL
                    AND {col} NOT LIKE '%+%'
                    AND {col} NOT LIKE '%Z'
                """))

                count = result.rowcount
                if count > 0:
                    print(f"  ✓ {col}: {count} timestamps updated")
                    total_updated += count

        print("\n" + "=" * 60)
        print(f"✓ Total: {total_updated} timestamps converted to UTC")
        print("=" * 60)

if __name__ == "__main__":
    main()
