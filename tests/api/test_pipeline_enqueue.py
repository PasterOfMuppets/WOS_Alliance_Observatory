from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from observatory.api import app
from observatory.worker import get_worker_state


def test_pipeline_enqueue(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text("samples: []\n")

    client = TestClient(app)
    response = client.post("/pipeline/enqueue", params={"manifest_path": str(manifest)})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"

    state = get_worker_state()
    assert state.running is False  # ensure enqueue doesn't auto start worker


def test_pipeline_enqueue_missing_file() -> None:
    client = TestClient(app)
    response = client.post("/pipeline/enqueue", params={"manifest_path": "/nonexistent/file.yaml"})
    assert response.status_code == 404
