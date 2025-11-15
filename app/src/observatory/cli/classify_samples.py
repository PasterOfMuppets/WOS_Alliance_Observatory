"""CLI for classifying screenshot samples via heuristic classifier."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from ..ocr import ScreenshotSample, load_manifest
from ..ocr.classifier import HeuristicClassifier


def classify_samples(manifest: Path, *, limit: int | None = None) -> list[dict[str, object]]:
    samples = load_manifest(manifest)
    classifier = HeuristicClassifier()
    results: list[dict[str, object]] = []
    count = 0
    for sample in samples:
        result = classifier.classify(sample)
        results.append(
            {
                "file": str(sample.path),
                "note": sample.note,
                "detected_type": result.detected_type.value,
                "confidence": round(result.confidence, 3),
                "sha256": result.loader_output.sha256,
                "width": result.loader_output.width,
                "height": result.loader_output.height,
            }
        )
        count += 1
        if limit and count >= limit:
            break
    return results


def print_results(results: Iterable[dict[str, object]]) -> None:
    for row in results:
        print(json.dumps(row, ensure_ascii=False))


def main() -> None:  # pragma: no cover - thin CLI wrapper
    parser = argparse.ArgumentParser(description="Classify screenshot samples")
    parser.add_argument("manifest", type=Path, help="Path to screenshot manifest YAML")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of samples")
    args = parser.parse_args()

    results = classify_samples(args.manifest, limit=args.limit)
    print_results(results)


if __name__ == "__main__":  # pragma: no cover
    main()
