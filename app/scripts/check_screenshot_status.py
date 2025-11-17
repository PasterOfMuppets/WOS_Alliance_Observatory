#!/usr/bin/env python3
"""Check the status of screenshots in the database."""

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
        print("SCREENSHOT STATUS SUMMARY")
        print("=" * 80)

        # Get count by status
        result = conn.execute(text("""
            SELECT status, COUNT(*) as count
            FROM screenshots
            GROUP BY status
            ORDER BY status
        """))

        rows = list(result)
        if rows:
            print("\nScreenshot counts by status:")
            for row in rows:
                print(f"  {row[0]}: {row[1]}")
        else:
            print("No screenshots found in database")

        print()
        print("=" * 80)
        print("PENDING SCREENSHOTS (if any)")
        print("=" * 80)

        result = conn.execute(text("""
            SELECT id, detected_type, uploader, source_path, created_at
            FROM screenshots
            WHERE status = 'PENDING'
            ORDER BY created_at
            LIMIT 20
        """))

        rows = list(result)
        if rows:
            print(f"\nFound {len(rows)} pending screenshots (showing first 20):")
            for row in rows:
                print(f"  ID {row[0]}: {row[1]} - {row[2]} - {row[3]} ({row[4]})")
        else:
            print("\n✓ No pending screenshots!")

        print()
        print("=" * 80)
        print("FAILED SCREENSHOTS (if any)")
        print("=" * 80)

        result = conn.execute(text("""
            SELECT id, detected_type, error_message, created_at
            FROM screenshots
            WHERE status = 'FAILED'
            ORDER BY created_at DESC
            LIMIT 10
        """))

        rows = list(result)
        if rows:
            print(f"\nFound {len(rows)} failed screenshots (showing last 10):")
            for row in rows:
                print(f"  ID {row[0]}: {row[1]}")
                print(f"    Error: {row[2]}")
                print(f"    Date: {row[3]}")
                print()
        else:
            print("\n✓ No failed screenshots!")

if __name__ == "__main__":
    main()
