# WOS Alliance Observatory
A lightweight, containerized OCR and analytics system for tracking Whiteout Survival alliance data.

## Local Stack (Two Containers)

Use Docker Compose to run the combined API/worker container plus the Caddy edge proxy:

```bash
docker compose up --build
```

The proxy exposes the FastAPI app on <http://localhost:8080>. Shut everything down with `docker compose down`.

After the containers are running for the first time, initialize the SQLite schema:

```bash
docker compose exec app alembic upgrade head
```

### Run Unit Tests

Mount the host `tests/` directory into the container and execute pytest:

```bash
docker compose run --rm \
  -v "$(pwd)/tests:/app/tests:ro" \
  app sh -c "pytest"
```

## Screenshot Samples

Reference captures live in `Screenshot_samples/`. Update `Screenshot_samples/manifest.yaml` with the detected `type` (values align with `observatory.db.enums.ScreenshotType`) and optional notes. Developers can load that manifest via `observatory.ocr.dataset.load_manifest` to feed classifiers and parsers during development.

### Optional AI OCR

Set `AI_OCR_ENABLED=1` and `OPENAI_API_KEY` in your environment to let the alliance-members parser call OpenAI's vision API instead of Tesseract. Configure the model via `AI_OCR_MODEL` (defaults to `gpt-4.1-mini`). Every API response is saved in the `ai_ocr_results` table for auditing before we upsert player stats. The parser falls back to Tesseract automatically if the API call fails.

### OCR Dependencies

Install the native Tesseract binary locally to enable real text extraction (e.g., `brew install tesseract` on macOS or `apt-get install tesseract-ocr` on Debian/Ubuntu). If the binary is missing, the pipeline logs a warning and falls back to heuristic parsing using filenames/notes only.

Classify samples with the heuristic CLI (mount the samples directory into the container):

```bash
docker compose run --rm \
  -v "$(pwd)/Screenshot_samples:/app/Screenshot_samples:ro" \
  app python -m observatory.cli.classify_samples Screenshot_samples/manifest.yaml --limit 5
```

Run the full pipeline (classifier + parser + JSON output) without touching the database:

```bash
docker compose run --rm \
  -v "$(pwd)/Screenshot_samples:/app/Screenshot_samples:ro" \
  app python -m observatory.cli.run_pipeline Screenshot_samples/manifest.yaml --limit 5
```

To queue a pipeline run inside the live API container (after `docker compose up --build`), call:

```bash
curl -X POST "http://localhost:8080/pipeline/enqueue?manifest_path=/app/Screenshot_samples/manifest.yaml&limit=5"
```
