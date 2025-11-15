"""CLI to run the OCR pipeline and print parsed output."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..ocr import load_manifest
from ..ocr.pipeline import OcrPipeline


def main() -> None:  # pragma: no cover - thin CLI
    parser = argparse.ArgumentParser(description="Run OCR pipeline against manifest")
    parser.add_argument("manifest", type=Path, help="Path to screenshot manifest YAML")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit on number of samples")
    args = parser.parse_args()

    pipeline = OcrPipeline()
    samples = load_manifest(args.manifest)
    if args.limit is not None:
        samples = samples[: args.limit]

    for result in pipeline.process_many(samples):
        output = {
            "file": str(result.sample.path),
            "detected_type": result.classification.detected_type.value,
            "confidence": result.classification.confidence,
            "parsed": result.parsed.payload,
            "text_preview": result.text[:160],
        }
        print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
