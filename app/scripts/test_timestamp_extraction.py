#!/usr/bin/env python3
"""Test timestamp extraction from screenshot."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from observatory.ocr.timestamp_extractor import extract_timestamp

# Test with the problematic file
test_file = "Screenshot_20251115_140601_Whiteout Survival.jpg"

# Try extraction
timestamp = extract_timestamp(Path(test_file))

if timestamp:
    print(f"✓ Extracted timestamp: {timestamp}")
    print(f"  Type: {type(timestamp)}")
    print(f"  Timezone info: {timestamp.tzinfo}")
    print(f"  Is timezone-aware: {timestamp.tzinfo is not None}")
else:
    print("✗ Failed to extract timestamp")
