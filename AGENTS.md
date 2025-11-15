# Repository Guidelines

## Project Structure & Module Organization
The repo currently houses planning docs (`README.md`, `design.md`, `WOS_Observatory_Design.md`) plus a pre-created `.venv` for local tooling. Runtime code now sits in `app/` (FastAPI API + background worker under `src/observatory`) and `proxy/` (Caddy config for TLS/edge routing). OCR helpers (image loader, future classifiers) live under `app/src/observatory/ocr`. Tests should mirror the package path under `tests/<module>` once implemented, and sample screenshots belong in `assets/screenshots/{inbox,processed}` to reflect the ingestion flow described in the design docs.

## Build, Test, and Development Commands
- `source .venv/bin/activate` — enter the shared virtual environment before touching dependencies.
- `pip install -r app/requirements.txt` — sync the combined API/worker container.
- `docker compose up --build` — build both the `app` and `proxy` containers; the API listens on `localhost:8080` via Caddy.
- `docker compose logs -f app` — inspect background worker activity.
- `pytest tests -m "not slow"` — run unit/integration tests while skipping GPU-heavy OCR cases.
- `pytest tests/ocr -m slow --tesseract /usr/local/bin/tesseract` — execute the full OCR parity suite when changing parsing logic.
- `docker compose run --rm -v "$(pwd)/Screenshot_samples:/app/Screenshot_samples:ro" app python -m observatory.cli.classify_samples Screenshot_samples/manifest.yaml --limit 10` — smoke-test the heuristic classifier against curated captures.
- `docker compose run --rm -v "$(pwd)/Screenshot_samples:/app/Screenshot_samples:ro" app python -m observatory.cli.run_pipeline Screenshot_samples/manifest.yaml --limit 10` — execute the full pipeline and review parsed JSON before persisting data.
- `curl -X POST "http://localhost:8080/pipeline/enqueue?manifest_path=/app/Screenshot_samples/manifest.yaml&limit=10"` — enqueue a run in the background worker while the stack is up.

## Coding Style & Naming Conventions
Use 4-space indentation, Black formatting, and Ruff linting; keep files under 400 lines when practical. Keep FastAPI routers under `observatory/api_<feature>.py`, SQLAlchemy models in PascalCase, and screenshot classifier modules in `snake_case` (e.g., `bear_events.py`). Place constants in `observatory/settings.py`, typed via `pydantic` settings models. Keep curated screenshot listings in `Screenshot_samples/manifest.yaml` so OCR tests can target real captures. Alliance roster parsing can optionally use OpenAI vision; all raw responses are stored in `ai_ocr_results` for traceability.

## Testing Guidelines
Favor pytest fixtures for sample OCR payloads; store golden JSON extracts per screenshot type in `tests/fixtures/<type>.json`. Minimum coverage for backend + worker should stay above 85%, and every parser change needs a regression test named `test_<screen_type>_<scenario>`. Mock filesystem and Tesseract paths with `tmp_path` to keep CI hermetic. Run tests inside the app container with `docker compose run --rm -v "$(pwd)/tests:/app/tests:ro" app sh -c "pytest"`. Install the native Tesseract binary locally (or in CI) for full-fidelity OCR; without it, parsers fall back to heuristic text matching. To exercise the OpenAI-based flow, export `AI_OCR_ENABLED=1` and `OPENAI_API_KEY` before running the pipeline CLI.

## Commit & Pull Request Guidelines
Adopt Conventional Commits (`feat: add bear trap parser`, `fix: normalize furnace levels`). Each PR must link to a design section or issue, describe schema changes, note migrations, and include before/after screenshots for UI-facing work. Request review from both backend and OCR owners whenever data extraction or schema files move in lockstep.

## Security & Configuration Tips
Store secrets in `.env` (never commit) and load them through `observatory.settings`. Restrict uploaded assets to PNG/JPG under 5 MB and purge processed screenshots as outlined in the design docs. Always run `docker compose exec app alembic upgrade head` before deploying schema changes.
