#!/usr/bin/env python3

"""Check for duplicate foundry entries in the database."""

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

        print("ALEMBIC MIGRATION VERSION")

        print("=" * 80)

        result = conn.execute(text("SELECT * FROM alembic_version"))

        for row in result:
            print(f"Current version: {row[0]}")

        print()

        print("=" * 80)

        print("DUPLICATE FOUNDRY SIGNUPS")

        print("=" * 80)

        result = conn.execute(text("""

            SELECT foundry_event_id, player_id, COUNT(*) as count

            FROM foundry_signups

            GROUP BY foundry_event_id, player_id

            HAVING COUNT(*) > 1

            ORDER BY count DESC

            LIMIT 20

        """))

        rows = list(result)

        if rows:

            print(f"Found {len(rows)} duplicate signup combinations:")

            for row in rows:
                print(f"  Event {row[0]}, Player {row[1]}: {row[2]} duplicates")

        else:

            print("No duplicate signups found!")

        print()

        print("=" * 80)

        print("DUPLICATE FOUNDRY RESULTS")

        print("=" * 80)

        result = conn.execute(text("""

            SELECT foundry_event_id, player_id, COUNT(*) as count

            FROM foundry_results

            GROUP BY foundry_event_id, player_id

            HAVING COUNT(*) > 1

            ORDER BY count DESC

            LIMIT 20

        """))

        rows = list(result)

        if rows:

            print(f"Found {len(rows)} duplicate result combinations:")

            for row in rows:
                print(f"  Event {row[0]}, Player {row[1]}: {row[2]} duplicates")

        else:

            print("No duplicate results found!")

        print()

        print("=" * 80)

        print("TABLE SCHEMA - foundry_signups")

        print("=" * 80)

        result = conn.execute(text("""

            SELECT sql FROM sqlite_master

            WHERE type='table' AND name='foundry_signups'

        """))

        for row in result:
            print(row[0])

        print()

        print("=" * 80)

        print("TABLE SCHEMA - foundry_results")

        print("=" * 80)

        result = conn.execute(text("""

            SELECT sql FROM sqlite_master

            WHERE type='table' AND name='foundry_results'

        """))

        for row in result:
            print(row[0])

        print()


if __name__ == "__main__":
    main()

