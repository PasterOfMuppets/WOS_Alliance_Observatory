"""High-level OCR engine combining loader, classifier, and parsers."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .dataset import load_manifest
from .pipeline import OcrPipeline, PipelineResult


@dataclass
class OcrEngine:
    pipeline: OcrPipeline

    def run_manifest(self, manifest_path: Path, limit: int | None = None) -> list[PipelineResult]:
        samples = load_manifest(manifest_path)
        if limit is not None:
            samples = samples[:limit]
        return list(self.pipeline.process_many(samples))
