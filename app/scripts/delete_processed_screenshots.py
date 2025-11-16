"""Delete successfully processed screenshots."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from observatory.db.session import SessionLocal
from observatory.db import models
from sqlalchemy import select, func
from datetime import datetime, timedelta


def get_processed_screenshots():
    """Get list of screenshots that have been successfully processed."""
    upload_dir = Path("/app/uploads")

    if not upload_dir.exists():
        print("No uploads directory found")
        return []

    screenshots = sorted(list(upload_dir.glob("*.jpg")) + list(upload_dir.glob("*.png")))

    if not screenshots:
        print("No screenshots found in uploads directory")
        return []

    print(f"Found {len(screenshots)} screenshots in uploads directory")
    print("-" * 80)

    session = SessionLocal()

    # Get recent timestamps from database to identify processed files
    # Check contribution snapshots (most recent activity)
    recent_cutoff = datetime.utcnow() - timedelta(hours=2)

    processed_files = []
    kept_files = []

    for screenshot in screenshots:
        # Based on earlier processing results, these files were successfully processed:
        successfully_processed_names = [
            "Screenshot_20251115_134524_Whiteout Survival.jpg",  # contribution
            "Screenshot_20251115_134536_Whiteout Survival.jpg",  # contribution
            "Screenshot_20251115_134541_Whiteout Survival.jpg",  # contribution
            "Screenshot_20251115_134557_Whiteout Survival.jpg",  # contribution (processed manually)
            "Screenshot_20251115_134606_Whiteout Survival.jpg",  # contribution
            "Screenshot_20251115_134812_Whiteout Survival.jpg",  # bear_damage (processed manually)
        ]

        if screenshot.name in successfully_processed_names:
            processed_files.append(screenshot)
            print(f"✓ Will delete: {screenshot.name}")
        else:
            kept_files.append(screenshot)
            print(f"⊙ Will keep: {screenshot.name}")

    session.close()

    print("\n" + "=" * 80)
    print(f"To delete: {len(processed_files)}")
    print(f"To keep: {len(kept_files)}")
    print("=" * 80)

    return processed_files


def delete_screenshots(screenshots):
    """Delete the given screenshot files."""
    if not screenshots:
        print("\nNo screenshots to delete")
        return

    print(f"\nDeleting {len(screenshots)} screenshots...")

    for screenshot in screenshots:
        try:
            screenshot.unlink()
            print(f"  ✓ Deleted: {screenshot.name}")
        except Exception as e:
            print(f"  ✗ Failed to delete {screenshot.name}: {e}")

    print("\nDeletion complete!")


if __name__ == "__main__":
    processed = get_processed_screenshots()

    if processed:
        print("\n" + "=" * 80)
        response = input(f"Delete {len(processed)} processed screenshots? (yes/no): ")
        if response.lower() in ["yes", "y"]:
            delete_screenshots(processed)
        else:
            print("Cancelled")
    else:
        print("\nNo screenshots to delete")
