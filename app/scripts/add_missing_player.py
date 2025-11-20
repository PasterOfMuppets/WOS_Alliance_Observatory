#!/usr/bin/env python3
"""Manually add a player to the database."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytz
from datetime import datetime
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from observatory.db import models
from observatory.settings import settings

def main():
    """Add a player to the database."""
    if len(sys.argv) < 2:
        print("Usage: python3 add_missing_player.py <player_name> [power] [furnace_level]")
        print("\nExamples:")
        print('  python3 add_missing_player.py "†-WRATH-†"')
        print('  python3 add_missing_player.py "xOsaツKȲA" 150000000 28')
        sys.exit(1)

    player_name = sys.argv[1]
    power = int(sys.argv[2]) if len(sys.argv) > 2 else None
    furnace_level = int(sys.argv[3]) if len(sys.argv) > 3 else None

    engine = create_engine(settings.database_url)

    with Session(engine) as session:
        # Check if player already exists
        existing = session.execute(
            select(models.Player).where(
                models.Player.alliance_id == 1,
                models.Player.name == player_name
            )
        ).scalar_one_or_none()

        if existing:
            print(f"❌ Player '{player_name}' already exists (ID: {existing.id})")
            print(f"   Power: {existing.current_power:,}" if existing.current_power else "   Power: N/A")
            print(f"   Furnace: FC{existing.current_furnace}" if existing.current_furnace else "   Furnace: N/A")
            return

        # Create new player
        now = datetime.now(pytz.UTC)
        new_player = models.Player(
            alliance_id=1,
            name=player_name,
            current_power=power,
            current_furnace=furnace_level,
            created_at=now,
            updated_at=now
        )

        session.add(new_player)
        session.commit()

        print(f"✅ Successfully added player: {player_name} (ID: {new_player.id})")
        if power:
            print(f"   Power: {power:,}")
        if furnace_level:
            print(f"   Furnace: FC{furnace_level}")

        print("\nPlayer is now available for matching in future screenshot uploads.")

if __name__ == "__main__":
    main()
