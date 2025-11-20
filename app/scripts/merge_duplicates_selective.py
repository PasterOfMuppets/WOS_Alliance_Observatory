#!/usr/bin/env python3
"""Merge specific duplicate groups while skipping others."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import difflib
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from observatory.db import models
from observatory.settings import settings

def find_duplicates(players, threshold=0.70):
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

def merge_players(session: Session, keep_id: int, merge_ids: list[int]):
    """Merge duplicate players into one, handling duplicate history records."""

    # For history tables with unique constraints, delete conflicting records first
    # Unique constraints: (player_id, captured_at)
    for table in ["player_power_history", "player_furnace_history"]:
        # Delete records from merge_ids that would conflict with keep_id
        session.execute(text(f"""
            DELETE FROM {table}
            WHERE player_id IN ({','.join(map(str, merge_ids))})
            AND captured_at IN (
                SELECT captured_at FROM {table} WHERE player_id = :keep_id
            )
        """), {"keep_id": keep_id})

    # Now update remaining records
    tables = [
        "bear_scores",
        "foundry_results",
        "foundry_signups",
        "ac_signups",
        "contribution_snapshots",
        "player_power_history",
        "player_furnace_history",
    ]

    for table in tables:
        update_query = text(
            f"UPDATE {table} SET player_id = :keep_id WHERE player_id IN ({','.join(map(str, merge_ids))})"
        )
        session.execute(update_query, {"keep_id": keep_id})

    # Delete duplicate player records
    for player_id in merge_ids:
        session.execute(text("DELETE FROM players WHERE id = :id"), {"id": player_id})

def main():
    """Merge duplicates, skipping group 4 (Mar vs Marra - different players)."""

    # Groups to skip (1-indexed)
    skip_groups = [4]  # Mar vs Marra are different players

    engine = create_engine(settings.database_url)

    print("=" * 80)
    print("SELECTIVE DUPLICATE MERGER")
    print("=" * 80)

    with Session(engine) as session:
        players = session.execute(
            select(models.Player)
            .where(models.Player.alliance_id == 1)
            .order_by(models.Player.name)
        ).scalars().all()

        duplicates = find_duplicates(players, 0.70)

        print(f"\nFound {len(duplicates)} groups of potential duplicates.")
        print(f"Skipping group(s): {', '.join(map(str, skip_groups))}")
        print()

        merged_count = 0
        for group_num, group in enumerate(duplicates, 1):
            # Check if we should skip this group
            if group_num in skip_groups:
                print(f"\nGroup {group_num}: SKIPPED (different players)")
                for i, player in enumerate(group):
                    power = f"{player.current_power:,}" if player.current_power else "N/A"
                    furnace = f"FC{player.current_furnace}" if player.current_furnace else "N/A"
                    marker = "KEEP" if i == 0 else "SKIP"
                    print(f"  {marker}: [{player.id:3d}] '{player.name}' (Power: {power}, {furnace})")
                continue

            # Merge this group
            print(f"\nGroup {group_num}: MERGING")
            for i, player in enumerate(group):
                power = f"{player.current_power:,}" if player.current_power else "N/A"
                furnace = f"FC{player.current_furnace}" if player.current_furnace else "N/A"
                marker = "→ KEEP" if i == 0 else "  merge"
                print(f"  {marker} [{player.id:3d}] '{player.name}' (Power: {power}, {furnace})")

            keep_id = group[0].id
            merge_ids = [p.id for p in group[1:]]

            merge_players(session, keep_id, merge_ids)
            merged_count += len(merge_ids)

        session.commit()

        print(f"\n{'Summary':-^80}")
        print(f"Groups processed: {len(duplicates) - len(skip_groups)}")
        print(f"Groups skipped: {len(skip_groups)}")
        print(f"Players merged: {merged_count}")
        print(f"\n✓ Merge completed successfully!")

if __name__ == "__main__":
    main()
