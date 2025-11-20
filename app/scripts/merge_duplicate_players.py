#!/usr/bin/env python3
"""Merge duplicate players into a single player record."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import difflib
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from observatory.db import models
from observatory.settings import settings

def find_duplicates(players, threshold=0.80):
    """Find potential duplicate players based on name similarity."""
    duplicates = []
    checked = set()

    for i, player1 in enumerate(players):
        if player1.id in checked:
            continue

        matches = [player1]
        for player2 in players[i+1:]:
            if player2.id in checked:
                continue

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

def merge_players(session: Session, keep_id: int, merge_ids: list[int], dry_run: bool = True):
    """
    Merge duplicate players into one.

    Args:
        session: Database session
        keep_id: Player ID to keep
        merge_ids: List of player IDs to merge into keep_id
        dry_run: If True, don't commit changes
    """
    # Tables with player_id foreign key
    tables = [
        "bear_scores",
        "foundry_results",
        "foundry_signups",
        "ac_signups",
        "contribution_snapshots",
        "player_power_history",
        "player_furnace_history",
    ]

    print(f"\n{'Merge Plan':-^80}")
    print(f"Keep player ID: {keep_id}")
    print(f"Merge player IDs: {', '.join(map(str, merge_ids))}")
    print()

    total_records = 0
    for table in tables:
        count_query = text(f"SELECT COUNT(*) FROM {table} WHERE player_id IN ({','.join(map(str, merge_ids))})")
        count = session.execute(count_query).scalar()

        if count > 0:
            print(f"  {table:30s}: {count:4d} records to update")
            total_records += count

            if not dry_run:
                update_query = text(
                    f"UPDATE {table} SET player_id = :keep_id WHERE player_id IN ({','.join(map(str, merge_ids))})"
                )
                session.execute(update_query, {"keep_id": keep_id})

    print(f"\n  {'Total records to migrate:':<30s} {total_records:4d}")

    if not dry_run:
        # Delete duplicate player records
        for player_id in merge_ids:
            session.execute(text("DELETE FROM players WHERE id = :id"), {"id": player_id})

        session.commit()
        print(f"\n✓ Merge completed! Deleted {len(merge_ids)} duplicate player(s).")
    else:
        print(f"\n⚠ DRY RUN - No changes made. Use --confirm to apply changes.")

def main():
    """Interactive duplicate player merger."""
    threshold = 0.80
    dry_run = True

    # Parse arguments
    if "--confirm" in sys.argv:
        dry_run = False
        sys.argv.remove("--confirm")

    if len(sys.argv) > 1 and sys.argv[1].replace(".", "").isdigit():
        threshold = float(sys.argv[1])

    engine = create_engine(settings.database_url)

    print("=" * 80)
    print(f"DUPLICATE PLAYER MERGER (Threshold: {threshold:.0%})")
    print("=" * 80)

    with Session(engine) as session:
        # Get all active players
        players = session.execute(
            select(models.Player)
            .where(models.Player.alliance_id == 1)
            .order_by(models.Player.name)
        ).scalars().all()

        # Find duplicates
        duplicates = find_duplicates(players, threshold)

        if not duplicates:
            print(f"\n✓ No duplicate players found at {threshold:.0%} similarity threshold!")
            return

        print(f"\nFound {len(duplicates)} groups of potential duplicates.\n")

        merged_count = 0
        for group_num, group in enumerate(duplicates, 1):
            print(f"\n{'Group ' + str(group_num):-^80}")

            for i, player in enumerate(group):
                power_str = f"{player.current_power:,}" if player.current_power else "N/A"
                furnace_str = f"FC{player.current_furnace}" if player.current_furnace else "N/A"

                similarity = 100.0 if i == 0 else difflib.SequenceMatcher(
                    None, group[0].name.lower(), player.name.lower()
                ).ratio() * 100

                marker = "→ KEEP" if i == 0 else "  merge"
                print(f"  {marker} [{player.id:3d}] '{player.name:30s}' | Power: {power_str:>15s} | {furnace_str:5s} | {similarity:.1f}%")

            # Auto-merge: keep first (usually shortest/cleanest name), merge others
            keep_id = group[0].id
            merge_ids = [p.id for p in group[1:]]

            merge_players(session, keep_id, merge_ids, dry_run=dry_run)
            merged_count += len(merge_ids)

        print(f"\n{'Summary':-^80}")
        print(f"Duplicate groups processed: {len(duplicates)}")
        print(f"Players merged: {merged_count}")

        if dry_run:
            print(f"\n⚠ This was a DRY RUN - no changes were made to the database.")
            print(f"\nTo apply these changes, run:")
            print(f"  docker compose exec app python3 /app/scripts/merge_duplicate_players.py --confirm")
        else:
            print(f"\n✓ All merges completed successfully!")

if __name__ == "__main__":
    main()
