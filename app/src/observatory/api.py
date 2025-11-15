"""FastAPI application entrypoint that orchestrates API + worker."""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db.session import get_session
from .worker import enqueue_pipeline_job, get_worker_state, start_worker, stop_worker

app = FastAPI(
    title="WOS Alliance Observatory",
    description="API + OCR worker container running inside a single image.",
    version="0.1.0",
)


@app.on_event("startup")
def startup_event() -> None:
    start_worker()


@app.on_event("shutdown")
def shutdown_event() -> None:
    stop_worker()


@app.get("/health", summary="Simple health probe")
def healthcheck() -> dict[str, object]:
    state = get_worker_state()
    return {
        "status": "ok" if state.running else "degraded",
        "processed_jobs": state.processed_jobs,
        "last_heartbeat": state.last_heartbeat,
    }


@app.get("/status/worker", summary="Worker state snapshot")
def worker_status() -> dict[str, object]:
    state = get_worker_state()
    return {
        "running": state.running,
        "processed_jobs": state.processed_jobs,
        "last_heartbeat": state.last_heartbeat,
        "last_result_preview": state.last_result_preview,
    }


@app.get("/db/health", summary="Database connectivity check")
def db_health(session: Session = Depends(get_session)) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.post("/pipeline/enqueue", summary="Enqueue OCR pipeline job")
def pipeline_enqueue(manifest_path: str, limit: int | None = None) -> dict[str, str]:
    manifest = Path(manifest_path)
    if not manifest.exists():
        raise HTTPException(status_code=404, detail=f"Manifest not found: {manifest}")
    enqueue_pipeline_job(manifest, limit=limit)
    return {"status": "queued", "manifest": str(manifest.resolve())}
