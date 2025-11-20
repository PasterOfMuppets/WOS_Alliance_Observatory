#!/usr/bin/env python3
"""Check for unmatched player names in recent screenshot processing."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from observatory.db import models
from observatory.settings import settings

def main():
    """Find unmatched players and suggest solutions."""
    engine = create_engine(settings.database_url)

    print("=" * 80)
    print("UNMATCHED PLAYERS DIAGNOSTIC TOOL")
    print("=" * 80)

    with Session(engine) as session:
        # Get alliance info
        alliance = session.execute(
            select(models.Alliance).where(models.Alliance.id == 1)
        ).scalar_one_or_none()

        if not alliance:
            print("ERROR: No alliance found with ID 1")
            return

        print(f"\nAlliance: {alliance.name} (ID: {alliance.id})")

        # Count existing players
        player_count = session.execute(
            select(models.Player)
            .where(models.Player.alliance_id == 1)
        ).scalars().all()

        print(f"Total players in database: {len(player_count)}")

        # Show all current players
        print(f"\n{'Current Players in Database:':-^80}")
        for i, player in enumerate(sorted(player_count, key=lambda p: p.name), 1):
            power_str = f"{player.current_power:,}" if player.current_power else "N/A"
            furnace_str = f"FC{player.current_furnace}" if player.current_furnace else "N/A"
            print(f"{i:3d}. {player.name:30s} | Power: {power_str:>15s} | {furnace_str}")

        # Check for players that might match the unmatched names
        print(f"\n{'Checking for Similar Names:':-^80}")
        unmatched_names = [
            "†-WRATH-†",
            "xOsaツKȲA"
        ]

        for unmatched in unmatched_names:
            print(f"\nLooking for matches to: '{unmatched}'")

            # Try exact match
            exact_match = session.execute(
                select(models.Player).where(
                    models.Player.alliance_id == 1,
                    models.Player.name == unmatched
                )
            ).scalar_one_or_none()

            if exact_match:
                print(f"  ✓ FOUND exact match: {exact_match.name} (ID: {exact_match.id})")
            else:
                print(f"  ✗ NOT FOUND in database")

                # Try fuzzy matching
                from observatory.db.player_matching import fuzzy_match_player
                fuzzy_player, similarity = fuzzy_match_player(session, 1, unmatched, threshold=0.70)

                if fuzzy_player:
                    print(f"  ~ Fuzzy match: '{fuzzy_player.name}' (similarity: {similarity:.2%})")
                else:
                    print(f"  ~ No fuzzy matches found (threshold: 70%)")

        # Check recent screenshots
        print(f"\n{'Recent Screenshot Processing:':-^80}")
        recent_screenshots = session.execute(
            text("""
                SELECT source_path, detected_type, status, created_at, error_message
                FROM screenshots
                ORDER BY created_at DESC
                LIMIT 10
            """)
        ).fetchall()

        if recent_screenshots:
            for ss in recent_screenshots:
                status_icon = "✓" if ss.status == "success" else "✗"
                filename = Path(ss.source_path).name if ss.source_path else "N/A"
                print(f"{status_icon} {filename:50s} | {ss.detected_type:20s} | Status: {ss.status}")
                if ss.error_message:
                    print(f"   Error: {ss.error_message}")
        else:
            print("No recent screenshots found")

        print(f"\n{'Recommendations:':-^80}")
        print("""
1. Upload an alliance member roster screenshot to add missing players
   - This should include the full member list with power and furnace levels

2. Or manually add players using the helper script:
   docker compose exec app python3 /app/scripts/add_missing_player.py "†-WRATH-†"
   docker compose exec app python3 /app/scripts/add_missing_player.py "†-WRATH-†" 150000000 28

3. Or directly via SQL:
   docker compose exec app sqlite3 /data/observatory.db

   INSERT INTO players (alliance_id, name, current_power, current_furnace, created_at, updated_at)
   VALUES (1, '†-WRATH-†', 0, NULL, datetime('now'), datetime('now'));

4. Check if player names in the database match exactly:
   - Special characters: †, ツ, Ȳ
   - Spacing
   - Case sensitivity (though matching is case-insensitive)

5. For debugging, check logs:
   docker compose logs app | grep "Player not found"
   docker compose logs app | grep "Fuzzy matched"
        """)

if __name__ == "__main__":
    main()
