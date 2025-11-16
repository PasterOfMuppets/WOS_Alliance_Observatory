"""Process all existing uploaded screenshots with rate limiting."""
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from observatory.screenshot_processor import ScreenshotProcessor
from observatory.db.session import SessionLocal


def process_all_uploads_with_delay():
    """Process all screenshots in /app/uploads directory with delays to avoid rate limits."""
    upload_dir = Path("/app/uploads")

    if not upload_dir.exists():
        print("No uploads directory found")
        return

    screenshots = list(upload_dir.glob("*.jpg")) + list(upload_dir.glob("*.png"))

    if not screenshots:
        print("No screenshots found in uploads directory")
        return

    print(f"Found {len(screenshots)} screenshots to process")
    print("Processing with 3-second delays to avoid rate limits...")
    print("-" * 80)

    session = SessionLocal()
    processor = ScreenshotProcessor(alliance_id=1)

    results = {
        "success": 0,
        "failed": 0,
        "total_records": 0,
        "skipped": 0
    }

    for i, screenshot in enumerate(sorted(screenshots), 1):
        print(f"\n[{i}/{len(screenshots)}] Processing: {screenshot.name}")

        try:
            result = processor.process_screenshot(session, screenshot)

            if result["success"]:
                results["success"] += 1
                results["total_records"] += result["records_saved"]
                print(f"  ✓ Type: {result['type']}")
                print(f"  ✓ {result['message']}")
            else:
                if "already" in result["message"].lower():
                    results["skipped"] += 1
                    print(f"  ⊘ Type: {result['type']}")
                    print(f"  ⊘ {result['message']} (already processed)")
                else:
                    results["failed"] += 1
                    print(f"  ✗ Type: {result['type']}")
                    print(f"  ✗ {result['message']}")

        except Exception as e:
            if "rate limit" in str(e).lower():
                print(f"  ⏸ Rate limit hit, waiting 60 seconds...")
                time.sleep(60)
                # Retry this screenshot
                try:
                    result = processor.process_screenshot(session, screenshot)
                    if result["success"]:
                        results["success"] += 1
                        results["total_records"] += result["records_saved"]
                        print(f"  ✓ Retry successful: {result['message']}")
                    else:
                        results["failed"] += 1
                        print(f"  ✗ Retry failed: {result['message']}")
                except Exception as retry_error:
                    results["failed"] += 1
                    print(f"  ✗ Retry error: {retry_error}")
            else:
                results["failed"] += 1
                print(f"  ✗ Error: {e}")

        # Add delay between screenshots to avoid rate limits
        if i < len(screenshots):
            time.sleep(3)

    session.close()

    print("\n" + "=" * 80)
    print(f"Processing complete!")
    print(f"  Success: {results['success']}")
    print(f"  Failed: {results['failed']}")
    print(f"  Skipped (already processed): {results['skipped']}")
    print(f"  Total records saved: {results['total_records']}")
    print("=" * 80)


if __name__ == "__main__":
    process_all_uploads_with_delay()
