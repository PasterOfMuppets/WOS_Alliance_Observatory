#!/usr/bin/env python3
"""Run AI OCR against a screenshot and print the JSON players list."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from observatory.ocr.ai_client import OpenAIVisionExtractor


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OpenAI-based OCR on a screenshot")
    parser.add_argument("image", type=Path, help="Path to screenshot image")
    args = parser.parse_args()

    extractor = OpenAIVisionExtractor()
    players = extractor.extract_players(args.image)
    print(json.dumps({"players": players}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
