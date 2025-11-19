#!/usr/bin/env python3
"""
Automated duplicate detection script for all tables in the observatory database.

This script checks for duplicate records across all tables and reports findings.
Can be run manually or scheduled as a cron job.

Usage:
    python scripts/check_all_duplicates.py [--fix]

Options:
    --fix    Automatically fix duplicates (use with caution)
"""
import sys
import logging
from pathlib import Path

# Add parent directory to path to import observatory modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import text
from observatory.db.session import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def check_player_power_history_duplicates(session):
    """Check for duplicate power history entries."""
    logger.info("Checking player_power_history for duplicates...")

    result = session.execute(text("""
        SELECT player_id, captured_at, COUNT(*) as count
        FROM player_power_history
        GROUP BY player_id, captured_at
        HAVING COUNT(*) > 1
    """)).fetchall()

    if result:
        logger.warning(f"Found {len(result)} duplicate player power history entries:")
        for row in result[:10]:  # Show first 10
            logger.warning(f"  Player {row.player_id} at {row.captured_at}: {row.count} entries")
        if len(result) > 10:
            logger.warning(f"  ... and {len(result) - 10} more")
        return len(result)
    else:
        logger.info("✓ No duplicates found in player_power_history")
        return 0


def check_player_furnace_history_duplicates(session):
    """Check for duplicate furnace history entries."""
    logger.info("Checking player_furnace_history for duplicates...")

    result = session.execute(text("""
        SELECT player_id, captured_at, COUNT(*) as count
        FROM player_furnace_history
        GROUP BY player_id, captured_at
        HAVING COUNT(*) > 1
    """)).fetchall()

    if result:
        logger.warning(f"Found {len(result)} duplicate furnace history entries:")
        for row in result[:10]:
            logger.warning(f"  Player {row.player_id} at {row.captured_at}: {row.count} entries")
        if len(result) > 10:
            logger.warning(f"  ... and {len(result) - 10} more")
        return len(result)
    else:
        logger.info("✓ No duplicates found in player_furnace_history")
        return 0


def check_contribution_snapshots_duplicates(session):
    """Check for duplicate contribution snapshots."""
    logger.info("Checking contribution_snapshots for duplicates...")

    result = session.execute(text("""
        SELECT alliance_id, player_id, week_start_date, snapshot_date, COUNT(*) as count
        FROM contribution_snapshots
        GROUP BY alliance_id, player_id, week_start_date, snapshot_date
        HAVING COUNT(*) > 1
    """)).fetchall()

    if result:
        logger.warning(f"Found {len(result)} duplicate contribution snapshots:")
        for row in result[:10]:
            logger.warning(
                f"  Alliance {row.alliance_id}, Player {row.player_id}, "
                f"Week {row.week_start_date}, Snapshot {row.snapshot_date}: {row.count} entries"
            )
        if len(result) > 10:
            logger.warning(f"  ... and {len(result) - 10} more")
        return len(result)
    else:
        logger.info("✓ No duplicates found in contribution_snapshots")
        return 0


def check_bear_scores_duplicates(session):
    """Check for duplicate bear scores."""
    logger.info("Checking bear_scores for duplicates...")

    result = session.execute(text("""
        SELECT bear_event_id, player_id, COUNT(*) as count
        FROM bear_scores
        GROUP BY bear_event_id, player_id
        HAVING COUNT(*) > 1
    """)).fetchall()

    if result:
        logger.warning(f"Found {len(result)} duplicate bear scores:")
        for row in result[:10]:
            logger.warning(f"  Event {row.bear_event_id}, Player {row.player_id}: {row.count} entries")
        if len(result) > 10:
            logger.warning(f"  ... and {len(result) - 10} more")

        # Show details of first duplicate
        if result:
            first = result[0]
            details = session.execute(text("""
                SELECT id, score, rank, recorded_at
                FROM bear_scores
                WHERE bear_event_id = :event_id AND player_id = :player_id
                ORDER BY recorded_at
            """), {"event_id": first.bear_event_id, "player_id": first.player_id}).fetchall()

            logger.warning(f"  Example duplicate details (Event {first.bear_event_id}, Player {first.player_id}):")
            for detail in details:
                logger.warning(f"    ID {detail.id}: score={detail.score}, rank={detail.rank}, recorded={detail.recorded_at}")

        return len(result)
    else:
        logger.info("✓ No duplicates found in bear_scores")
        return 0


def check_ac_signups_duplicates(session):
    """Check for duplicate AC signups."""
    logger.info("Checking ac_signups for duplicates...")

    result = session.execute(text("""
        SELECT ac_event_id, player_id, COUNT(*) as count
        FROM ac_signups
        GROUP BY ac_event_id, player_id
        HAVING COUNT(*) > 1
    """)).fetchall()

    if result:
        logger.warning(f"Found {len(result)} duplicate AC signups:")
        for row in result[:10]:
            logger.warning(f"  Event {row.ac_event_id}, Player {row.player_id}: {row.count} entries")
        if len(result) > 10:
            logger.warning(f"  ... and {len(result) - 10} more")
        return len(result)
    else:
        logger.info("✓ No duplicates found in ac_signups")
        return 0


def check_foundry_signups_duplicates(session):
    """Check for duplicate foundry signups."""
    logger.info("Checking foundry_signups for duplicates...")

    result = session.execute(text("""
        SELECT foundry_event_id, player_id, COUNT(*) as count
        FROM foundry_signups
        GROUP BY foundry_event_id, player_id
        HAVING COUNT(*) > 1
    """)).fetchall()

    if result:
        logger.warning(f"Found {len(result)} duplicate foundry signups:")
        for row in result[:10]:
            logger.warning(f"  Event {row.foundry_event_id}, Player {row.player_id}: {row.count} entries")
        if len(result) > 10:
            logger.warning(f"  ... and {len(result) - 10} more")
        return len(result)
    else:
        logger.info("✓ No duplicates found in foundry_signups")
        return 0


def check_foundry_results_duplicates(session):
    """Check for duplicate foundry results."""
    logger.info("Checking foundry_results for duplicates...")

    result = session.execute(text("""
        SELECT foundry_event_id, player_id, COUNT(*) as count
        FROM foundry_results
        GROUP BY foundry_event_id, player_id
        HAVING COUNT(*) > 1
    """)).fetchall()

    if result:
        logger.warning(f"Found {len(result)} duplicate foundry results:")
        for row in result[:10]:
            logger.warning(f"  Event {row.foundry_event_id}, Player {row.player_id}: {row.count} entries")
        if len(result) > 10:
            logger.warning(f"  ... and {len(result) - 10} more")
        return len(result)
    else:
        logger.info("✓ No duplicates found in foundry_results")
        return 0


def check_all_duplicates():
    """Run all duplicate checks."""
    logger.info("=" * 60)
    logger.info("Starting comprehensive duplicate detection scan")
    logger.info("=" * 60)

    session = SessionLocal()
    total_issues = 0

    try:
        # Check each table
        total_issues += check_player_power_history_duplicates(session)
        total_issues += check_player_furnace_history_duplicates(session)
        total_issues += check_contribution_snapshots_duplicates(session)
        total_issues += check_bear_scores_duplicates(session)
        total_issues += check_ac_signups_duplicates(session)
        total_issues += check_foundry_signups_duplicates(session)
        total_issues += check_foundry_results_duplicates(session)

        logger.info("=" * 60)
        if total_issues == 0:
            logger.info("✓ ALL CLEAR - No duplicates found in any table!")
        else:
            logger.warning(f"⚠ FOUND {total_issues} duplicate issue(s) across tables")
            logger.warning("Run migrations to apply unique constraints and prevent future duplicates")
        logger.info("=" * 60)

        return total_issues

    finally:
        session.close()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Check for duplicate records in the database")
    parser.add_argument("--fix", action="store_true", help="Automatically fix duplicates (not implemented yet)")
    args = parser.parse_args()

    if args.fix:
        logger.error("Automatic fixing not implemented yet. Please run migrations instead.")
        sys.exit(1)

    total_issues = check_all_duplicates()
    sys.exit(0 if total_issues == 0 else 1)


if __name__ == "__main__":
    main()
