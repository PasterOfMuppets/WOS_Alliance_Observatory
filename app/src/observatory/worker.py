"""Background worker that can run OCR pipeline jobs."""
from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .ocr import load_manifest
from .ocr.pipeline import OcrPipeline

logger = logging.getLogger(__name__)


@dataclass
class WorkerState:
    running: bool = False
    processed_jobs: int = 0
    last_heartbeat: Optional[float] = None
    last_result_preview: Optional[dict[str, object]] = None
    thread: Optional[threading.Thread] = field(default=None, repr=False, compare=False)


@dataclass
class PipelineJob:
    manifest_path: Path
    limit: Optional[int] = None


_state = WorkerState()
_stop_event = threading.Event()
_job_queue: "queue.Queue[PipelineJob]" = queue.Queue()
_pipeline: Optional[OcrPipeline] = None


def _worker_loop(poll_interval: float = 5.0) -> None:
    logger.info("Worker loop started")
    global _pipeline
    _pipeline = OcrPipeline()

    while not _stop_event.is_set():
        try:
            job = _job_queue.get(timeout=poll_interval)
        except queue.Empty:
            _state.last_heartbeat = time.time()
            continue

        try:
            process_pipeline_job(job)
        except Exception as exc:  # pragma: no cover - log unexpected failures
            logger.exception("Failed processing job %s", job, exc_info=exc)
        finally:
            _job_queue.task_done()

    logger.info("Worker loop exiting")


def process_pipeline_job(job: PipelineJob) -> None:
    if _pipeline is None:
        logger.warning("Pipeline not initialized; skipping job")
        return

    if not job.manifest_path.exists():
        logger.warning("Manifest %s not found", job.manifest_path)
        return

    samples = load_manifest(job.manifest_path)
    if job.limit is not None:
        samples = samples[: job.limit]

    for result in _pipeline.process_many(samples):
        _state.processed_jobs += 1
        _state.last_result_preview = {
            "file": str(result.sample.path),
            "detected_type": result.classification.detected_type.value,
            "parsed": result.parsed.payload,
        }
        logger.info("Processed %s", _state.last_result_preview)
        if _stop_event.is_set():
            break

    _state.last_heartbeat = time.time()


def enqueue_pipeline_job(manifest_path: Path, limit: Optional[int] = None) -> None:
    _job_queue.put(PipelineJob(manifest_path=manifest_path, limit=limit))


def start_worker() -> WorkerState:
    if _state.running:
        return _state

    thread = threading.Thread(target=_worker_loop, name="observatory-worker", daemon=True)
    _stop_event.clear()
    thread.start()

    _state.running = True
    _state.thread = thread
    _state.last_heartbeat = time.time()
    return _state


def stop_worker() -> None:
    if not _state.running:
        return
    _stop_event.set()
    enqueue_pipeline_job(Path("."), limit=0)  # unblock queue
    if _state.thread and _state.thread.is_alive():
        _state.thread.join(timeout=5)
    _state.running = False
    _state.thread = None


def get_worker_state() -> WorkerState:
    return _state
