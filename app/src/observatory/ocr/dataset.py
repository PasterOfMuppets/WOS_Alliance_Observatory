"""Utilities for working with screenshot sample data sets."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import yaml

from ..db.enums import ScreenshotType


@dataclass(frozen=True)
class ScreenshotSample:
    """Represents a curated screenshot sample entry."""

    path: Path
    type: ScreenshotType
    note: str | None = None


def load_manifest(
    manifest_path: str | Path,
    *,
    base_dir: str | Path | None = None,
) -> list[ScreenshotSample]:
    """Load screenshot samples from a YAML manifest."""

    manifest = Path(manifest_path)
    if not manifest.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest}")

    base = Path(base_dir) if base_dir else manifest.parent
    data = yaml.safe_load(manifest.read_text()) or {}
    entries: Sequence[dict] = data.get("samples", [])
    samples: list[ScreenshotSample] = []
    for entry in entries:
        file_name = entry.get("file")
        if not file_name:
            continue
        type_name = entry.get("type", ScreenshotType.UNKNOWN.value)
        note = entry.get("note")
        sample_path = (base / file_name).resolve()
        samples.append(
            ScreenshotSample(
                path=sample_path,
                type=ScreenshotType(type_name),
                note=note,
            )
        )
    return samples


def discover_samples(
    directory: str | Path,
    *,
    patterns: Iterable[str] = ("*.png", "*.jpg", "*.jpeg"),
    default_type: ScreenshotType = ScreenshotType.UNKNOWN,
    note: str | None = None,
) -> list[ScreenshotSample]:
    """Scan a directory for screenshots without a manifest."""

    base = Path(directory)
    if not base.is_dir():
        raise NotADirectoryError(f"Sample directory not found: {base}")

    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(sorted(base.glob(pattern)))

    return [
        ScreenshotSample(path=path.resolve(), type=default_type, note=note)
        for path in paths
    ]
