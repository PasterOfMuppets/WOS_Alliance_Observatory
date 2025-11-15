from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from observatory.cli.run_pipeline import main as run_pipeline_main


def _make_image_bytes(size=(100, 50), color=(100, 50, 200), fmt="PNG") -> bytes:
    image = Image.new("RGB", size, color)
    buffer = BytesIO()
    image.save(buffer, fmt)
    return buffer.getvalue()


def test_run_pipeline_cli(tmp_path, monkeypatch, capsys):
    sample_dir = tmp_path / "shots"
    sample_dir.mkdir()
    img_path = sample_dir / "members_lane.png"
    img_path.write_bytes(_make_image_bytes())

    manifest = sample_dir / "manifest.yaml"
    manifest.write_text(
        """
        samples:
          - file: members_lane.png
        """.strip()
    )

    args = ["program", str(manifest), "--limit", "1"]
    monkeypatch.setattr("sys.argv", args)

    run_pipeline_main()
    captured = capsys.readouterr()
    assert "members_lane.png" in captured.out
