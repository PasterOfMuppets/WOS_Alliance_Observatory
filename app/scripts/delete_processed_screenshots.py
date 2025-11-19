#!/usr/bin/env python3
"""
Delete old processed screenshots based on retention policy.

This script deletes screenshots that have been successfully processed and are
older than the configured retention period. Failed screenshots are kept longer
for debugging purposes.

Usage:
    python scripts/delete_processed_screenshots.py [--dry-run] [--include-failed]

Options:
    --dry-run         Show what would be deleted without actually deleting
    --include-failed  Also delete old failed screenshots
"""
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
import argparse

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from observatory.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_old_screenshots(upload_dir: Path, retention_days: int, include_failed: bool = False) -> tuple[list[Path], list[Path]]:
    """
    Find screenshots older than retention period.

    Returns:
        Tuple of (successful_screenshots, failed_screenshots)
    """
    if not upload_dir.exists():
        logger.info(f"Upload directory does not exist: {upload_dir}")
        return [], []

    all_screenshots = sorted(
        list(upload_dir.glob("*.jpg")) +
        list(upload_dir.glob("*.png")) +
        list(upload_dir.glob("*.jpeg"))
    )

    if not all_screenshots:
        logger.info(f"No screenshots found in {upload_dir}")
        return [], []

    logger.info(f"Found {len(all_screenshots)} total screenshot(s) in {upload_dir}")

    # Calculate cutoff time
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    logger.info(f"Retention cutoff: {cutoff.isoformat()} ({retention_days} days ago)")

    successful_old = []
    failed_old = []

    for screenshot in all_screenshots:
        # Get file modification time
        file_mtime = datetime.fromtimestamp(screenshot.stat().st_mtime, tz=timezone.utc)

        if file_mtime < cutoff:
            # Heuristic: assume files with "error" or "failed" in name are failures
            # In production, you might track this in database
            if "error" in screenshot.name.lower() or "failed" in screenshot.name.lower():
                failed_old.append((screenshot, file_mtime))
                logger.debug(f"Old failed screenshot: {screenshot.name} (age: {file_mtime})")
            else:
                successful_old.append((screenshot, file_mtime))
                logger.debug(f"Old successful screenshot: {screenshot.name} (age: {file_mtime})")

    logger.info(f"Found {len(successful_old)} old successful screenshot(s)")
    if include_failed:
        logger.info(f"Found {len(failed_old)} old failed screenshot(s)")

    # Extract just the paths
    successful_paths = [s[0] for s in successful_old]
    failed_paths = [s[0] for s in failed_old] if include_failed else []

    return successful_paths, failed_paths


def delete_screenshots(screenshots: list[Path], dry_run: bool = False) -> dict[str, int]:
    """
    Delete the given screenshot files.

    Returns:
        Dict with counts: {"deleted": N, "failed": M, "skipped": K}
    """
    if not screenshots:
        logger.info("No screenshots to delete")
        return {"deleted": 0, "failed": 0, "skipped": 0}

    logger.info(f"{'[DRY RUN] Would delete' if dry_run else 'Deleting'} {len(screenshots)} screenshot(s)...")

    deleted = 0
    failed = 0
    skipped = 0

    for screenshot in screenshots:
        try:
            if not screenshot.exists():
                logger.warning(f"  ⊙ Skipped (not found): {screenshot.name}")
                skipped += 1
                continue

            if dry_run:
                logger.info(f"  [DRY RUN] Would delete: {screenshot.name} ({screenshot.stat().st_size} bytes)")
                deleted += 1
            else:
                size = screenshot.stat().st_size
                screenshot.unlink()
                logger.info(f"  ✓ Deleted: {screenshot.name} ({size} bytes)")
                deleted += 1

        except Exception as e:
            logger.error(f"  ✗ Failed to delete {screenshot.name}: {e}")
            failed += 1

    logger.info(f"\nSummary: {deleted} deleted, {failed} failed, {skipped} skipped")
    return {"deleted": deleted, "failed": failed, "skipped": skipped}


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Delete old processed screenshots")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting")
    parser.add_argument("--include-failed", action="store_true", help="Also delete old failed screenshots")
    parser.add_argument("--retention-days", type=int, help=f"Override retention days (default: {settings.screenshot_retention_days})")
    args = parser.parse_args()

    upload_dir = Path("/app/uploads")
    retention_days = args.retention_days if args.retention_days else settings.screenshot_retention_days

    logger.info("=" * 80)
    logger.info("Screenshot Cleanup Script")
    logger.info("=" * 80)
    logger.info(f"Upload directory: {upload_dir}")
    logger.info(f"Retention period: {retention_days} days")
    logger.info(f"Include failed: {args.include_failed}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("=" * 80)

    successful, failed = get_old_screenshots(upload_dir, retention_days, args.include_failed)

    total_to_delete = successful + failed

    if not total_to_delete:
        logger.info("\n✓ No old screenshots to delete")
        return 0

    logger.info(f"\nFound {len(total_to_delete)} screenshot(s) to delete:")
    logger.info(f"  - {len(successful)} successful (older than {retention_days} days)")
    if args.include_failed:
        logger.info(f"  - {len(failed)} failed (older than {retention_days} days)")

    if not args.dry_run:
        logger.info("=" * 80)
        response = input(f"\nDelete {len(total_to_delete)} screenshot(s)? (yes/no): ")
        if response.lower() not in ["yes", "y"]:
            logger.info("Cancelled")
            return 1

    logger.info("")
    result = delete_screenshots(total_to_delete, dry_run=args.dry_run)

    logger.info("=" * 80)
    logger.info("Cleanup complete!")
    logger.info("=" * 80)

    return 0 if result["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
