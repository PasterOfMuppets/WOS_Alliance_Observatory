from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from observatory.ocr.dataset import discover_samples, load_manifest
from observatory.db.enums import ScreenshotType


def _make_image_bytes(size=(100, 50), color=(0, 128, 255), fmt="PNG") -> bytes:
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, fmt)
    return buffer.getvalue()


def test_load_manifest(tmp_path: Path) -> None:
    sample_dir = tmp_path / "samples"
    sample_dir.mkdir()
    img_path = sample_dir / "example.png"
    img_path.write_bytes(_make_image_bytes())

    manifest = sample_dir / "manifest.yaml"
    manifest.write_text(
        """
        samples:
          - file: example.png
            type: alliance_members
            note: Test entry
        """.strip()
    )

    samples = load_manifest(manifest)
    assert len(samples) == 1
    sample = samples[0]
    assert sample.path == img_path.resolve()
    assert sample.type == ScreenshotType.ALLIANCE_MEMBERS
    assert sample.note == "Test entry"


def test_discover_samples(tmp_path: Path) -> None:
    sample_dir = tmp_path / "samples"
    sample_dir.mkdir()
    (sample_dir / "one.png").write_bytes(_make_image_bytes())
    (sample_dir / "two.jpg").write_bytes(_make_image_bytes(fmt="JPEG"))

    samples = discover_samples(sample_dir, note="auto")
    assert len(samples) == 2
    assert all(sample.type == ScreenshotType.UNKNOWN for sample in samples)
    assert all(sample.note == "auto" for sample in samples)


def test_discover_samples_missing_dir(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        discover_samples(tmp_path / "missing")
