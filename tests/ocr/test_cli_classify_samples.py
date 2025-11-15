from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from observatory.cli.classify_samples import classify_samples
from observatory.db.enums import ScreenshotType


def _make_image_bytes(size=(100, 50), color=(10, 200, 10), fmt="PNG") -> bytes:
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, fmt)
    return buffer.getvalue()


def test_classify_samples(tmp_path: Path, monkeypatch) -> None:
    sample_dir = tmp_path / "samples"
    sample_dir.mkdir()
    img_path = sample_dir / "foobar_contribution.png"
    img_path.write_bytes(_make_image_bytes())

    manifest = sample_dir / "manifest.yaml"
    manifest.write_text(
        """
        samples:
          - file: foobar_contribution.png
            type: unknown
            note: contribution board capture
        """.strip()
    )

    results = classify_samples(manifest)
    assert len(results) == 1
    row = results[0]
    assert row["detected_type"] == ScreenshotType.CONTRIBUTION.value
    assert row["width"] == 100
    assert row["note"] == "contribution board capture"
