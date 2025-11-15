# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WOS Alliance Observatory is a containerized OCR and analytics system for tracking Whiteout Survival alliance data. It extracts player statistics (power, furnace level, contribution, bear event scores, AC lane assignments) from uploaded game screenshots and maintains historical timelines for multiple alliances.

The system runs as a FastAPI application with an embedded background worker, using SQLite for storage and Tesseract (or optional OpenAI vision API) for OCR. It's designed for minimal load and low compute requirements.

## Architecture

### Container Structure
- **app**: Combined FastAPI API + background worker in a single container
  - FastAPI server on port 8000 (internal)
  - Embedded threading-based worker for OCR pipeline jobs
  - SQLite database mounted at `/data/observatory.db`
- **proxy**: Caddy reverse proxy exposing the API on localhost:8080

### Core Modules
- `app/src/observatory/api.py` - FastAPI application with health checks and pipeline endpoints
- `app/src/observatory/worker.py` - Background worker with job queue for OCR processing
- `app/src/observatory/ocr/pipeline.py` - OCR pipeline orchestration (classify → extract → parse)
- `app/src/observatory/ocr/classifier.py` - Screenshot type detection (heuristic-based)
- `app/src/observatory/ocr/parsers.py` - Type-specific data extraction (alliance members, contribution, bear events, AC lanes)
- `app/src/observatory/ocr/text_extractor.py` - Tesseract/pytesseract wrapper
- `app/src/observatory/ocr/ai_client.py` - Optional OpenAI vision API client for alliance member parsing
- `app/src/observatory/db/models.py` - SQLAlchemy ORM models
- `app/src/observatory/settings.py` - Pydantic settings with .env support

### OCR Pipeline Flow
1. **Classification**: Heuristic classifier examines image dimensions, filenames, and notes to detect screenshot type
2. **Text Extraction**: Tesseract extracts text from the image (or OpenAI vision API if enabled)
3. **Type Inference**: Extracted text is analyzed to refine/confirm screenshot type
4. **Parsing**: Type-specific parser extracts structured data (player names, power values, scores, etc.)
5. **Storage**: Parsed data stored in `ai_ocr_results` table for audit trail

### Supported Screenshot Types
- **ALLIANCE_MEMBERS**: Player name, power, furnace level
- **CONTRIBUTION**: Player name, weekly contribution, ranking
- **BEAR_EVENT**: Bear trap ID (1 or 2), player name, score, rank
- **AC_LANES**: Lane (left/middle/right), player name, AC power, battle order
- **UNKNOWN**: Failed classification or unsupported types

## Common Commands

### Local Development
```bash
# Enter virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r app/requirements.txt

# Start the full stack (API + proxy)
docker compose up --build

# Initialize database schema (first time only)
docker compose exec app alembic upgrade head

# View worker logs
docker compose logs -f app

# Shut down
docker compose down
```

### Running Tests
```bash
# Run unit tests (inside container, mounts host tests directory)
docker compose run --rm \
  -v "$(pwd)/tests:/app/tests:ro" \
  app sh -c "pytest"

# Run tests excluding slow OCR tests
pytest tests -m "not slow"

# Run full OCR test suite with Tesseract
pytest tests/ocr -m slow --tesseract /usr/local/bin/tesseract
```

### OCR Development & Testing
```bash
# Classify sample screenshots (heuristic only, no OCR)
docker compose run --rm \
  -v "$(pwd)/Screenshot_samples:/app/Screenshot_samples:ro" \
  app python3 -m observatory.cli.classify_samples Screenshot_samples/manifest.yaml --limit 10

# Run full pipeline (classify + OCR + parse) without DB persistence
docker compose run --rm \
  -v "$(pwd)/Screenshot_samples:/app/Screenshot_samples:ro" \
  app python3 -m observatory.cli.run_pipeline Screenshot_samples/manifest.yaml --limit 10

# Enqueue pipeline job in live worker (after docker compose up)
curl -X POST "http://localhost:8080/pipeline/enqueue?manifest_path=/app/Screenshot_samples/manifest.yaml&limit=10"

# Check worker status
curl http://localhost:8080/status/worker
```

### Database Migrations
```bash
# Create a new migration after model changes
docker compose exec app alembic revision --autogenerate -m "description"

# Apply pending migrations
docker compose exec app alembic upgrade head

# Rollback one migration
docker compose exec app alembic downgrade -1
```

## Screenshot Samples & Manifest

Reference screenshots live in `Screenshot_samples/` with metadata in `Screenshot_samples/manifest.yaml`. The manifest format:

```yaml
samples:
  - path: Screenshot_samples/alliance_members_001.png
    type: ALLIANCE_MEMBERS
    notes: "Sample roster capture"
```

Use `observatory.ocr.dataset.load_manifest` to load samples programmatically. The manifest `type` field must match `observatory.db.enums.ScreenshotType` enum values.

## AI OCR (Optional)

To enable OpenAI vision API for alliance member parsing:

```bash
# Set environment variables
export AI_OCR_ENABLED=1
export OPENAI_API_KEY=sk-...
export AI_OCR_MODEL=gpt-4.1-mini  # optional, defaults to gpt-4.1-mini

# Run pipeline with AI OCR enabled
docker compose run --rm \
  -v "$(pwd)/Screenshot_samples:/app/Screenshot_samples:ro" \
  app python3 -m observatory.cli.run_pipeline Screenshot_samples/manifest.yaml --limit 5
```

All AI OCR responses are saved in the `ai_ocr_results` table for auditing before data is persisted. The parser automatically falls back to Tesseract if the API call fails.

## Database Schema Notes

### Player Identity Resolution
- Players are stored in `players` table with `alliance_id` + `name` unique constraint
- Player rename handling: The design documents describe a `player_aliases` table for tracking name changes and fuzzy matching, but this is not yet implemented in the current schema
- Historical data linked via `player_id` in history tables

### Bear Events
- Each bear trap run creates a new `bear_events` record (trap_id 1 or 2)
- Minimum 47-hour cooldown between runs per trap
- All bear scores preserved permanently in `bear_scores` table
- Design documents describe this schema, but current implementation may differ - check `app/src/observatory/db/models.py` for actual schema

### Current Tables
- `alliances` - Alliance records
- `players` - Player records with alliance FK
- `player_power_history` - Power snapshots over time
- `player_furnace_history` - Furnace level snapshots
- `event_stats` - Event-specific metrics (contribution, bear scores, etc.)
- `screenshots` - Upload tracking with status/error fields
- `ai_ocr_results` - AI OCR response audit trail

## Important Testing Notes

- OCR tests require native Tesseract binary: `brew install tesseract` (macOS) or `apt-get install tesseract-ocr` (Linux)
- Without Tesseract, the pipeline logs a warning and falls back to heuristic parsing
- Store golden JSON extracts in `tests/fixtures/<type>.json` for parser regression tests
- Use `tmp_path` fixture to mock filesystem operations
- Minimum coverage target: 85%

## Configuration & Secrets

- All secrets go in `.env` (gitignored) at repository root
- Settings loaded via `observatory.settings.Settings` (Pydantic)
- Docker Compose automatically passes `.env` to the app container
- Key settings:
  - `DATABASE_URL` - defaults to `sqlite:////data/observatory.db`
  - `AI_OCR_ENABLED` - enable OpenAI vision API (default: false)
  - `AI_OCR_MODEL` - model name (default: gpt-4.1-mini)
  - `OPENAI_API_KEY` - required if AI_OCR_ENABLED=1

## Development Workflow

1. Make code changes in `app/src/observatory/`
2. Run relevant tests: `docker compose run --rm -v "$(pwd)/tests:/app/tests:ro" app sh -c "pytest tests/<module>"`
3. Test full pipeline with samples: `docker compose run --rm -v "$(pwd)/Screenshot_samples:/app/Screenshot_samples:ro" app python3 -m observatory.cli.run_pipeline Screenshot_samples/manifest.yaml`
4. If schema changed: `docker compose exec app alembic revision --autogenerate -m "description"` then `alembic upgrade head`
5. Rebuild and restart stack: `docker compose up --build`

## File Upload Constraints

- Accept only PNG/JPG formats
- Max upload size: 5MB
- Screenshots deleted after successful processing (production)
- Store uploader ID, timestamp, detected type, and results in `screenshots` table
