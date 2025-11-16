"""Process all existing uploaded screenshots."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from observatory.screenshot_processor import ScreenshotProcessor
from observatory.db.session import SessionLocal


def process_all_uploads():
    """Process all screenshots in /app/uploads directory."""
    upload_dir = Path("/app/uploads")

    if not upload_dir.exists():
        print("No uploads directory found")
        return

    screenshots = list(upload_dir.glob("*.jpg")) + list(upload_dir.glob("*.png"))

    if not screenshots:
        print("No screenshots found in uploads directory")
        return

    print(f"Found {len(screenshots)} screenshots to process")
    print("-" * 80)

    session = SessionLocal()
    processor = ScreenshotProcessor(alliance_id=1)

    results = {
        "success": 0,
        "failed": 0,
        "total_records": 0
    }

    for screenshot in sorted(screenshots):
        print(f"\nProcessing: {screenshot.name}")

        try:
            result = processor.process_screenshot(session, screenshot)

            if result["success"]:
                results["success"] += 1
                results["total_records"] += result["records_saved"]
                print(f"  ✓ Type: {result['type']}")
                print(f"  ✓ {result['message']}")
            else:
                results["failed"] += 1
                print(f"  ✗ Type: {result['type']}")
                print(f"  ✗ {result['message']}")

        except Exception as e:
            results["failed"] += 1
            print(f"  ✗ Error: {e}")

    session.close()

    print("\n" + "=" * 80)
    print(f"Processing complete!")
    print(f"  Success: {results['success']}")
    print(f"  Failed: {results['failed']}")
    print(f"  Total records saved: {results['total_records']}")
    print("=" * 80)


if __name__ == "__main__":
    process_all_uploads()
