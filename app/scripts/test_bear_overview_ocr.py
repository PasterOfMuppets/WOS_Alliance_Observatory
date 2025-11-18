#!/usr/bin/env python3
"""Test bear overview OCR extraction."""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytesseract
from PIL import Image
from observatory.ocr.bear_overview_parser import parse_bear_overview

# Test file
test_file = Path("Screenshot_20251117_191833_Whiteout Survival.jpg")

if not test_file.exists():
    print(f"Error: {test_file} not found")
    print(f"Current directory: {Path.cwd()}")
    sys.exit(1)

print("=" * 60)
print(f"Testing OCR extraction on: {test_file}")
print("=" * 60)

# Extract text using Tesseract
print("\n1. Extracting text with Tesseract...")
image = Image.open(test_file)
text = pytesseract.image_to_string(image)

print("\nExtracted text:")
print("-" * 60)
print(text)
print("-" * 60)

# Parse the data
print("\n2. Parsing extracted data...")
data = parse_bear_overview(text)

print("\nParsed results:")
print(f"  trap_id: {data.get('trap_id')}")
print(f"  rally_count: {data.get('rally_count')}")
print(f"  total_damage: {data.get('total_damage')}")

if data.get("trap_id"):
    print("\n✓ Successfully extracted bear overview data!")
else:
    print("\n✗ Failed to extract trap_id - screenshot may not be a bear overview")
