#!/usr/bin/env python3
"""Find potential duplicate players in the database."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import difflib
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from observatory.db import models
from observatory.settings import settings

def load_exclusions():
    """Load player pairs that should not be merged."""
    exclusions = set()
    exclusion_file = Path(__file__).parent / "not_duplicates.txt"

    if exclusion_file.exists():
        with open(exclusion_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split(',')
                    if len(parts) >= 2:
                        try:
                            id1, id2 = int(parts[0]), int(parts[1])
                            exclusions.add((min(id1, id2), max(id1, id2)))
                        except ValueError:
                            pass
    return exclusions

def find_duplicates(players, threshold=0.80):
    """Find potential duplicate players based on name similarity."""
    exclusions = load_exclusions()
    duplicates = []
    checked = set()

    for i, player1 in enumerate(players):
        if player1.id in checked:
            continue

        matches = [player1]
        for player2 in players[i+1:]:
            if player2.id in checked:
                continue

            # Check if this pair is in the exclusion list
            pair = (min(player1.id, player2.id), max(player1.id, player2.id))
            if pair in exclusions:
                continue

            # Calculate similarity
            similarity = difflib.SequenceMatcher(
                None,
                player1.name.lower(),
                player2.name.lower()
            ).ratio()

            if similarity >= threshold:
                matches.append(player2)
                checked.add(player2.id)

        if len(matches) > 1:
            duplicates.append(matches)
            checked.add(player1.id)

    return duplicates

def main():
    """Find and display duplicate players."""
    threshold = 0.80  # 80% similarity
    if len(sys.argv) > 1:
        threshold = float(sys.argv[1])

    engine = create_engine(settings.database_url)

    print("=" * 100)
    print(f"DUPLICATE PLAYER FINDER (Threshold: {threshold:.0%})")
    print("=" * 100)

    with Session(engine) as session:
        # Get all active players
        players = session.execute(
            select(models.Player)
            .where(models.Player.alliance_id == 1)
            .order_by(models.Player.name)
        ).scalars().all()

        print(f"\nTotal players in alliance: {len(players)}")

        # Find duplicates
        duplicates = find_duplicates(players, threshold)

        if not duplicates:
            print(f"\n✓ No duplicate players found at {threshold:.0%} similarity threshold!")
            return

        print(f"\n⚠ Found {len(duplicates)} groups of potential duplicates:\n")

        total_duplicates = 0
        for group_num, group in enumerate(duplicates, 1):
            print(f"{'Group ' + str(group_num):-^100}")

            # Calculate similarities between all pairs in group
            for i, player in enumerate(group):
                power_str = f"{player.current_power:,}" if player.current_power else "N/A"
                furnace_str = f"FC{player.current_furnace}" if player.current_furnace else "N/A"

                # Show similarity to first player in group
                if i == 0:
                    similarity = 100.0
                else:
                    similarity = difflib.SequenceMatcher(
                        None,
                        group[0].name.lower(),
                        player.name.lower()
                    ).ratio() * 100

                print(f"  {player.id:3d}. '{player.name:30s}' | Power: {power_str:>15s} | {furnace_str:5s} | {similarity:.1f}% match")
                total_duplicates += 1

            print()

        print(f"{'Summary':-^100}")
        print(f"Duplicate groups: {len(duplicates)}")
        print(f"Total duplicate entries: {total_duplicates - len(duplicates)} (keeping 1 per group)")
        print()

        print(f"{'Next Steps':-^100}")
        print("""
To merge duplicates, you have two options:

1. Use the merge script (recommended):
   docker compose exec app python3 /app/scripts/merge_duplicate_players.py

2. Manual SQL (for specific cases):
   docker compose exec app sqlite3 /data/observatory.db

   -- Example: Merge "W R A T H" (ID 3) into "WRATH" (ID 2)
   UPDATE bear_scores SET player_id = 2 WHERE player_id = 3;
   UPDATE foundry_results SET player_id = 2 WHERE player_id = 3;
   UPDATE foundry_signups SET player_id = 2 WHERE player_id = 3;
   UPDATE ac_signups SET player_id = 2 WHERE player_id = 3;
   UPDATE contribution_snapshots SET player_id = 2 WHERE player_id = 3;
   UPDATE player_power_history SET player_id = 2 WHERE player_id = 3;
   UPDATE player_furnace_history SET player_id = 2 WHERE player_id = 3;
   DELETE FROM players WHERE id = 3;

Note: Adjust the threshold to find more/fewer matches:
  python3 find_duplicate_players.py 0.70  # More sensitive (70%)
  python3 find_duplicate_players.py 0.90  # Less sensitive (90%)
        """)

if __name__ == "__main__":
    main()
