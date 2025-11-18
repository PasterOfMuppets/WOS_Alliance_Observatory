# WOS Alliance Observatory - Fixes and Features

This document outlines bugs, improvements, and new features for the WOS Alliance Observatory project. Items are organized by priority and include detailed technical specifications for implementation.

---

## Priority 1: Critical Bugs & UX Issues

### 1.1 Bear Events Edit Button Too Large
**Location:** `app/src/observatory/templates/events_bear.html:228`

**Current Behavior:**
- Edit button displays as `✏️ Edit` with full text and emoji
- Takes up significant space in the Date & Time column
- Visually distracting and clutters the UI

**Desired Behavior:**
- Replace with small icon-only button (just ✏️ or pencil SVG icon)
- Smaller size (e.g., 20x20px)
- Tooltip on hover showing "Edit event time"
- Better visual hierarchy - icon should be subtle

**Technical Details:**
```html
<!-- Current -->
<button onclick="editEventTime(...)" style="padding: 2px 6px; font-size: 12px;">
    ✏️ Edit
</button>

<!-- Proposed -->
<button onclick="editEventTime(...)"
        class="edit-icon-btn"
        title="Edit event time"
        style="padding: 4px; font-size: 14px; border: none; background: transparent; cursor: pointer;">
    ✏️
</button>
```

**Files to Modify:**
- `app/src/observatory/templates/events_bear.html`
- Optionally add CSS class to `app/src/observatory/static/style.css`

---

### 1.2 Remove Screenshot Taker from Bear Damage Results
**Location:** `app/src/observatory/ocr/ai_client.py` (BEAR_EVENT_PROMPT) and `app/src/observatory/db/bear_operations.py`

**Current Behavior:**
- Screenshot taker appears in the damage rankings as "Unranked" at the bottom
- This person didn't actually participate in the bear event
- Creates misleading data (shows more participants than actually contributed)

**Desired Behavior:**
- Filter out players with rank = "Unranked" or rank = null during OCR parsing
- Do not create `BearScore` records for unranked players
- Only save players who actually participated (have a numeric rank)

**Technical Details:**
1. Update `save_bear_event_ocr()` in `bear_operations.py`:
   ```python
   # Skip unranked players
   rank = player_data.get("rank")
   if rank is None or rank == "Unranked":
       logger.debug(f"Skipping unranked player {player_name}")
       continue
   ```

2. Consider updating the AI OCR prompt to explicitly exclude unranked players

**Files to Modify:**
- `app/src/observatory/db/bear_operations.py:127-229`
- Optionally: `app/src/observatory/ocr/ai_client.py:54-84` (BEAR_EVENT_PROMPT)

---

### 1.3 Rate Limiting on Bulk Screenshot Uploads
**Location:** `app/src/observatory/screenshot_processor.py` and upload handling

**Current Behavior:**
- Multiple screenshots uploaded simultaneously
- All processed immediately in parallel
- OpenAI API rate limit exceeded (429 errors)
- Error: `Rate limit reached for gpt-4o-mini... Please try again in 297ms`

**Desired Behavior:**
- Add configurable delay between screenshot processing (default: 10-15 seconds)
- Process screenshots sequentially with delay when using AI OCR
- Show progress indicator to user (e.g., "Processing 3 of 10...")
- Graceful handling of rate limit errors with automatic retry

**Technical Details:**

**Option A: Sequential Processing with Delay (Recommended)**
```python
# In screenshot_processor.py
import time

PROCESSING_DELAY_SECONDS = 12  # Configurable

for screenshot in screenshots:
    result = process_screenshot(screenshot)
    if ai_ocr_was_used:
        time.sleep(PROCESSING_DELAY_SECONDS)
```

**Option B: Queue-based Processing**
- Use background worker queue (already exists)
- Add rate limiting to worker
- Process one job every 10-15 seconds

**Option C: Token Bucket Rate Limiter**
```python
from threading import Lock
from time import time, sleep

class RateLimiter:
    def __init__(self, requests_per_minute=5):
        self.rpm = requests_per_minute
        self.interval = 60.0 / requests_per_minute
        self.last_request = 0
        self.lock = Lock()

    def acquire(self):
        with self.lock:
            elapsed = time() - self.last_request
            if elapsed < self.interval:
                sleep(self.interval - elapsed)
            self.last_request = time()
```

**Configuration:**
Add to `app/src/observatory/settings.py`:
```python
ai_ocr_rate_limit_delay: int = Field(12, alias="AI_OCR_RATE_LIMIT_DELAY")
```

**Files to Modify:**
- `app/src/observatory/screenshot_processor.py`
- `app/src/observatory/settings.py`
- `app/src/observatory/api.py` (upload endpoint)

---

## Priority 2: Data Quality & Consistency

### 2.1 Timezone Handling in SQLite
**Status:** Partially fixed, needs comprehensive solution

**Current State:**
- Fixed 1,232+ naive timestamps across all tables
- SQLite strips timezone info when storing DateTime values
- Requires manual fixes whenever new data is inserted
- Custom `TZDateTime` type created but not yet applied to models

**Desired Solution:**

**Option A: Apply Custom TZDateTime Type (Recommended)**
```python
# In models.py
from .custom_types import TZDateTime

class BearEvent(Base):
    __tablename__ = "bear_events"
    # Change from DateTime(timezone=True) to TZDateTime
    started_at: Mapped[datetime] = mapped_column(TZDateTime, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(TZDateTime, nullable=True)
```

Apply to ALL DateTime columns across all models.

**Option B: Migration to PostgreSQL**
- PostgreSQL has proper timezone support
- Better for production deployments
- More robust for multi-user scenarios
- Add docker-compose.postgres.yml

**Option C: Database Triggers (SQLite-specific)**
- Create AFTER INSERT/UPDATE triggers to append +00:00
- Automatically fix any naive timestamps
- Performance impact minimal

**Recommendation:** Use Option A (Custom Type) + create migration to update all model columns.

**Files to Modify:**
- `app/src/observatory/db/models.py` (all DateTime columns)
- Create new Alembic migration

---

### 2.2 Duplicate Detection and Prevention
**Status:** Fixed for contributions, bear events, and foundry. Need comprehensive solution.

**Current State:**
- Manual fixes applied for existing duplicates
- Unique constraints added to prevent future duplicates
- No automated detection or cleanup

**Desired Solution:**
1. **Automated Duplicate Detection Script**
   - Run on startup or schedule
   - Check all tables for duplicates
   - Log warnings
   - Located: `app/scripts/check_all_duplicates.py`

2. **Duplicate Prevention Checklist**
   - ✅ `player_power_history`: Unique on (player_id, captured_at)
   - ✅ `player_furnace_history`: Unique on (player_id, captured_at)
   - ✅ `contribution_snapshots`: Unique on (alliance_id, player_id, week_start_date, snapshot_date)
   - ✅ `foundry_signups`: Unique on (foundry_event_id, player_id)
   - ✅ `foundry_results`: Unique on (foundry_event_id, player_id)
   - ❌ `bear_scores`: NO unique constraint (can have duplicate scores)
   - ✅ `ac_signups`: Need to check

3. **Bear Scores Duplicate Handling**
   - Decide: Should same player have multiple scores in same event?
   - If no: Add unique constraint (bear_event_id, player_id)
   - If yes: Document why duplicates are allowed

**Files to Create:**
- `app/scripts/check_all_duplicates.py`
- Update constraints in models if needed

---

### 2.3 Screenshot Classification Accuracy
**Location:** `app/src/observatory/screenshot_processor.py:46-67`

**Current Issues:**
- Bear overview vs bear damage confusion (just fixed)
- No fallback when AI classification fails
- No confidence score returned
- No ability to manually override classification

**Desired Improvements:**

1. **Add Heuristic Fallback**
   - If AI fails, use text-based detection
   - Check for key phrases in filename or OCR text
   - Example: "overview" in filename → bear_overview

2. **Return Confidence Score**
   ```python
   {
       "type": "bear_overview",
       "confidence": 0.95
   }
   ```

3. **Manual Override UI**
   - Add dropdown on upload results page
   - "Wrong type detected? Select correct type:"
   - Re-process button

4. **Classification History/Audit**
   - Store original classification + any manual overrides
   - Track accuracy over time

**Files to Modify:**
- `app/src/observatory/screenshot_processor.py`
- `app/src/observatory/db/models.py` (add classification_confidence field)
- `app/src/observatory/templates/upload.html`

---

## Priority 3: Features & Enhancements

### 3.1 Manual Data Correction Interface

**Feature:** Allow users to edit/delete incorrect data entries

**Components:**

1. **Delete Bear Score**
   - Add delete button (🗑️) next to each player in bear event details
   - Confirmation dialog
   - API: `DELETE /api/events/bear/{event_id}/scores/{score_id}`

2. **Delete Entire Bear Event**
   - Add delete button in event header
   - Delete cascade to all scores
   - API: `DELETE /api/events/bear/{event_id}`

3. **Edit Player Power/Furnace Manually**
   - Click-to-edit on roster page
   - Update current values + add history entry
   - API: `PATCH /api/players/{player_id}`

4. **Merge Duplicate Players**
   - UI to identify potential duplicates (fuzzy name matching)
   - Merge functionality: combine history, update foreign keys
   - API: `POST /api/players/{player_id}/merge/{duplicate_id}`

**Files to Create:**
- `app/src/observatory/api.py` (new endpoints)
- Update templates with delete/edit buttons

---

### 3.2 Data Export Functionality

**Feature:** Export data to CSV/Excel for external analysis

**Export Options:**

1. **Bear Event Data**
   - Event details (trap, date, rallies, damage)
   - All scores for event
   - Format: CSV, JSON

2. **Player Power History**
   - Select player(s)
   - Date range
   - Include: date, power, furnace level
   - Chart: power growth over time

3. **Weekly Contribution Reports**
   - Weekly contribution per player
   - Compare weeks
   - Top contributors

4. **Alliance Rankings**
   - Export current rankings
   - Historical trends

**API Endpoints:**
```
GET /api/export/bear-events?format=csv
GET /api/export/player-history/{player_id}?format=csv&start_date=...&end_date=...
GET /api/export/contributions?week=...&format=csv
```

**Files to Create:**
- `app/src/observatory/api_export.py`
- Add export buttons to templates

---

### 3.3 Improved Screenshot Upload Progress

**Feature:** Real-time upload progress with status updates

**Current State:**
- Upload all files at once
- Process in background
- Only see final results

**Desired State:**
- Progress bar during upload
- Real-time status updates during processing
- Per-file status (uploading → processing → complete/failed)
- Estimated time remaining

**Technical Implementation:**

1. **WebSocket or Server-Sent Events (SSE)**
   ```python
   from fastapi import WebSocket

   @app.websocket("/ws/upload/{upload_id}")
   async def upload_progress(websocket: WebSocket, upload_id: str):
       await websocket.accept()
       # Stream progress updates
       await websocket.send_json({
           "filename": "...",
           "status": "processing",
           "progress": 0.5
       })
   ```

2. **Polling Endpoint**
   ```python
   @app.get("/api/upload/{upload_id}/status")
   async def get_upload_status(upload_id: str):
       return {
           "total": 10,
           "completed": 3,
           "failed": 1,
           "in_progress": 6,
           "files": [...]
       }
   ```

3. **Frontend Updates**
   - Progress bar with percentage
   - File-by-file list with status icons
   - Ability to cancel upload

**Files to Modify:**
- `app/src/observatory/api.py`
- `app/src/observatory/templates/upload.html`
- Create new WebSocket handler

---

### 3.4 Admin Panel

**Feature:** Administrative interface for user/alliance management

**Components:**

1. **User Management**
   - List all users
   - Create/edit/delete users
   - Reset passwords
   - Assign default alliances
   - Set admin privileges

2. **Alliance Management**
   - Create/edit/delete alliances
   - Set alliance tags
   - View alliance statistics
   - Bulk operations

3. **System Settings**
   - Configure rate limits
   - Set screenshot timezone
   - Enable/disable AI OCR
   - View system health

4. **Database Maintenance**
   - Run duplicate detection
   - Run timezone fixes
   - View database size
   - Export/backup data

**Access Control:**
- Only admin users can access
- Separate admin dashboard route: `/admin`

**Files to Create:**
- `app/src/observatory/templates/admin/` (directory)
- `app/src/observatory/admin_api.py`
- Add admin middleware/decorators

---

### 3.5 Bear Event Notes/Comments

**Feature:** Add notes/comments to bear events

**Use Cases:**
- Record who led rallies
- Note special circumstances (low participation, rushed, etc.)
- Track improvements over time

**Implementation:**
```python
# In models.py
class BearEvent(Base):
    # ... existing fields
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
```

**UI:**
- Text area below event details
- Save button
- Display notes in event list (truncated)

**Files to Modify:**
- `app/src/observatory/db/models.py`
- `app/src/observatory/templates/events_bear.html`
- `app/src/observatory/api.py` (add update endpoint)

---

## Priority 4: Performance & Scalability

### 4.1 Database Indexes

**Current State:**
- Basic indexes on primary keys and foreign keys
- No composite indexes for common queries

**Recommended Indexes:**

```sql
-- Contribution snapshots: frequently queried by week
CREATE INDEX idx_contribution_week_alliance
ON contribution_snapshots(alliance_id, week_start_date);

-- Bear scores: frequently queried with event
CREATE INDEX idx_bear_scores_event_player
ON bear_scores(bear_event_id, player_id);

-- Power history: time-series queries
CREATE INDEX idx_power_history_player_time
ON player_power_history(player_id, captured_at DESC);

-- Event stats: filtering by type and time
CREATE INDEX idx_event_stats_type_time
ON event_stats(event_type, captured_at DESC);
```

**Files to Modify:**
- Create new Alembic migration: `app/alembic/versions/add_performance_indexes.py`

---

### 4.2 Screenshot Cleanup

**Feature:** Automatically delete processed screenshots

**Current State:**
- Screenshots accumulate in `/app/uploads/`
- No automatic cleanup
- Can fill disk over time

**Desired Behavior:**
- Delete screenshots after successful processing (configurable)
- Keep failed screenshots for debugging (X days)
- Manual cleanup option
- Configurable retention policy

**Configuration:**
```python
# In settings.py
screenshot_retention_days: int = Field(7, alias="SCREENSHOT_RETENTION_DAYS")
delete_successful_screenshots: bool = Field(True, alias="DELETE_SUCCESSFUL_SCREENSHOTS")
```

**Implementation:**
1. Update `screenshot_processor.py` to delete after success
2. Add scheduled cleanup job (cron or background task)
3. Add manual cleanup button in admin panel

**Files to Modify:**
- `app/src/observatory/screenshot_processor.py`
- `app/src/observatory/settings.py`
- Enhance existing `app/scripts/delete_processed_screenshots.py`

---

### 4.3 Caching Layer

**Feature:** Cache frequently accessed data

**Use Cases:**
- Alliance member lists (changes infrequently)
- Bear event summaries
- Contribution rankings
- Alliance power rankings

**Implementation Options:**

**Option A: Redis**
```python
from redis import Redis
from functools import wraps

redis_client = Redis(host='redis', port=6379)

def cache(ttl=300):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{args}:{kwargs}"
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
            result = await func(*args, **kwargs)
            redis_client.setex(cache_key, ttl, json.dumps(result))
            return result
        return wrapper
    return decorator

@app.get("/api/players")
@cache(ttl=600)  # Cache for 10 minutes
async def get_players():
    ...
```

**Option B: In-Memory Cache (simpler)**
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def get_alliance_members(alliance_id: int):
    ...
```

**Recommendation:** Start with Option B (lru_cache), upgrade to Redis if needed.

**Files to Modify:**
- `app/src/observatory/api.py`
- `docker-compose.yml` (add Redis service if using Option A)

---

## Priority 5: Code Quality & Maintenance

### 5.1 Comprehensive Test Suite

**Current State:**
- Minimal tests
- No integration tests
- No UI tests

**Desired Coverage:**

1. **Unit Tests**
   - OCR parsers: `tests/ocr/test_parsers.py`
   - Database operations: `tests/db/test_operations.py`
   - Timestamp handling: `tests/test_timestamps.py`

2. **Integration Tests**
   - Upload flow end-to-end
   - Bear event processing
   - API endpoints

3. **Test Fixtures**
   - Sample screenshots
   - Mock OCR responses
   - Database fixtures

**Test Organization:**
```
tests/
├── fixtures/
│   ├── screenshots/
│   └── json/
├── unit/
│   ├── test_bear_operations.py
│   ├── test_contribution_operations.py
│   └── test_parsers.py
├── integration/
│   ├── test_upload_flow.py
│   └── test_api.py
└── conftest.py
```

**Files to Create:**
- Full test suite under `tests/`
- Update `pytest.ini` configuration

---

### 5.2 API Documentation

**Feature:** Auto-generated API documentation

**Current State:**
- FastAPI provides automatic docs at `/docs`
- Minimal docstrings
- No usage examples

**Enhancements:**

1. **Improve Docstrings**
   ```python
   @app.get("/api/events/bear")
   async def get_bear_events(
       current_user: models.User = Depends(auth.get_current_active_user),
       session: Session = Depends(auth.get_session)
   ):
       """
       Get all bear events with scores, grouped by trap.

       Returns two lists of bear events (trap 1 and trap 2), each with:
       - Event details (trap_id, started_at, rally_count, total_damage)
       - Participant scores sorted by rank

       **Example Response:**
       ```json
       {
         "trap1_events": [...],
         "trap2_events": [...]
       }
       ```

       **Authorization:** Requires valid JWT token
       """
   ```

2. **Add OpenAPI Tags/Groups**
   ```python
   @app.get("/api/events/bear", tags=["Events"])
   @app.get("/api/players", tags=["Players"])
   ```

3. **Add Examples**
   ```python
   from pydantic import BaseModel, Field

   class BearEventResponse(BaseModel):
       id: int = Field(..., example=1)
       trap_id: int = Field(..., example=1)
       started_at: str = Field(..., example="2025-11-17T14:20:00+00:00")
   ```

**Files to Modify:**
- All API endpoints in `app/src/observatory/api.py`
- Create Pydantic models for request/response

---

### 5.3 Error Handling & Logging

**Current Issues:**
- Inconsistent error handling
- Minimal logging in some areas
- User-facing errors are too technical

**Improvements:**

1. **Structured Logging**
   ```python
   import structlog

   logger = structlog.get_logger()
   logger.info("processing_screenshot",
               filename=image_path.name,
               type=screenshot_type,
               alliance_id=alliance_id)
   ```

2. **Custom Exception Classes**
   ```python
   class OCRExtractionError(Exception):
       """Raised when OCR extraction fails"""
       pass

   class RateLimitError(Exception):
       """Raised when hitting API rate limits"""
       pass
   ```

3. **User-Friendly Error Messages**
   ```python
   try:
       result = process_screenshot()
   except RateLimitError:
       return {"error": "Too many requests. Please wait a moment and try again."}
   except OCRExtractionError:
       return {"error": "Could not read screenshot. Please ensure image is clear."}
   ```

4. **Error Tracking**
   - Integration with Sentry or similar
   - Log errors to dedicated error log file
   - Email alerts for critical errors

**Files to Modify:**
- `app/src/observatory/screenshot_processor.py`
- `app/src/observatory/api.py`
- Create `app/src/observatory/exceptions.py`

---

## Implementation Plan

### Phase 1: Critical Fixes (Week 1)
- [ ] 1.1 Bear Events Edit Button (2 hours)
- [ ] 1.2 Remove Unranked Players (3 hours)
- [ ] 1.3 Rate Limiting Fix (4 hours)
- [ ] 2.1 Apply TZDateTime Type (6 hours)

### Phase 2: Data Quality (Week 2)
- [ ] 2.2 Duplicate Detection Script (4 hours)
- [ ] 2.3 Screenshot Classification Improvements (5 hours)
- [ ] 4.2 Screenshot Cleanup (3 hours)

### Phase 3: Features (Week 3-4)
- [ ] 3.1 Manual Data Correction (8 hours)
- [ ] 3.2 Data Export (6 hours)
- [ ] 3.3 Upload Progress (8 hours)
- [ ] 3.5 Bear Event Notes (3 hours)

### Phase 4: Admin & Quality (Week 5)
- [ ] 3.4 Admin Panel (12 hours)
- [ ] 5.1 Test Suite (10 hours)
- [ ] 5.2 API Documentation (4 hours)
- [ ] 5.3 Error Handling (6 hours)

### Phase 5: Performance (Week 6)
- [ ] 4.1 Database Indexes (2 hours)
- [ ] 4.3 Caching Layer (6 hours)

---

## Technical Debt

### Items to Address Long-Term

1. **Database Migration to PostgreSQL**
   - Better timezone handling
   - Better performance for larger datasets
   - More robust for production

2. **Separate API and Worker**
   - Currently combined in one container
   - Better scalability with separate services
   - Use Celery or RQ for background tasks

3. **Frontend Framework**
   - Current: Vanilla JavaScript
   - Consider: Vue.js or React for better state management
   - Improved developer experience

4. **Authentication Improvements**
   - OAuth integration (Google, Discord)
   - Two-factor authentication
   - Session management improvements

5. **Mobile Responsiveness**
   - Current UI works on desktop
   - Needs optimization for mobile devices
   - Touch-friendly controls

---

## Configuration Reference

### Environment Variables to Add

```bash
# Rate Limiting
AI_OCR_RATE_LIMIT_DELAY=12  # seconds between AI OCR requests

# Screenshot Management
DELETE_SUCCESSFUL_SCREENSHOTS=true
SCREENSHOT_RETENTION_DAYS=7

# Performance
ENABLE_CACHING=true
CACHE_TTL_SECONDS=300

# Database
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Logging
LOG_LEVEL=INFO
STRUCTURED_LOGGING=true
ERROR_NOTIFICATION_EMAIL=admin@example.com
```

---

## Notes for Implementation

### Best Practices

1. **Always create database backups before schema changes**
   ```bash
   docker compose exec app sqlite3 /data/observatory.db .dump > backup_$(date +%Y%m%d).sql
   ```

2. **Test with sample data first**
   - Use `Screenshot_samples/` for testing
   - Don't test directly on production database

3. **Create migrations for all schema changes**
   ```bash
   docker compose exec app alembic revision --autogenerate -m "description"
   ```

4. **Update CLAUDE.md with new features**
   - Document new API endpoints
   - Update screenshot type descriptions
   - Add new configuration options

5. **Commit frequently with clear messages**
   - One feature per commit when possible
   - Reference this document in commit messages

### Testing Checklist

For each feature:
- [ ] Unit tests written and passing
- [ ] Manual testing with sample data
- [ ] Database migration tested (upgrade and downgrade)
- [ ] Documentation updated
- [ ] No new timezone issues introduced
- [ ] Error cases handled gracefully
- [ ] User-facing messages are clear
- [ ] Performance impact acceptable

---

## Questions for Clarification

1. **Priority ordering**: Is the order above (Priority 1-5) correct, or should anything be reordered?

2. **Bear event grouping**: The 24-hour window for grouping bear events - is this working well, or should it be configurable?

3. **Data retention**: How long should historical data be kept? Any archival requirements?

4. **Multi-alliance**: Will one user ever need to manage multiple alliances, or always one default?

5. **Player rename handling**: The design documents mention player_aliases table for tracking renames. Should this be implemented?

6. **Screenshot source**: Are all screenshots taken on the same device/timezone, or do multiple users upload from different timezones?

---

## High-Level Architecture Recommendations

### Current Architecture
```
┌─────────────────┐
│   Caddy Proxy   │ :8080
└────────┬────────┘
         │
┌────────▼────────┐
│   FastAPI App   │ :8000
│   + Worker      │
│   (Single Pod)  │
└────────┬────────┘
         │
┌────────▼────────┐
│  SQLite + Data  │ (Volume)
└─────────────────┘
```

### Recommended Future Architecture
```
┌─────────────────┐
│   Caddy Proxy   │ :8080
└────────┬────────┘
         │
┌────────▼────────────────────┐
│   FastAPI API Service       │ (Scaled)
│   - Serves HTTP requests    │
│   - Authentication          │
│   - Queues jobs             │
└────────┬────────────────────┘
         │
    ┌────▼────┐
    │  Redis  │ (Queue + Cache)
    └────┬────┘
         │
┌────────▼────────────────────┐
│   Worker Service            │ (Scaled)
│   - Processes OCR jobs      │
│   - Handles rate limiting   │
│   - Background tasks        │
└────────┬────────────────────┘
         │
┌────────▼────────────────────┐
│   PostgreSQL Database       │
│   - Proper timezone support │
│   - Better performance      │
│   - ACID guarantees         │
└─────────────────────────────┘
```

**Benefits:**
- Scale API and worker independently
- Better fault tolerance
- Improved rate limit handling
- Production-ready architecture

**Migration Path:**
1. Add Redis for job queue (Phase 3)
2. Separate worker from API (Phase 4)
3. Migrate to PostgreSQL (Phase 5)
4. Each step is independent and reversible

---

## Conclusion

This document provides a comprehensive roadmap for improving the WOS Alliance Observatory. All items are actionable and include technical details for implementation.

**Estimated Total Effort:** 80-100 hours of development

**Recommended Team:**
- 1 Backend Developer (FastAPI, SQLAlchemy, database)
- 1 Frontend Developer (HTML/CSS/JavaScript, UI/UX)
- Access to Claude Code (Web) for implementation assistance

**Next Steps:**
1. Review and prioritize items
2. Clarify any questions above
3. Begin with Phase 1 (Critical Fixes)
4. Set up project tracking (GitHub Issues, Linear, etc.)
5. Implement and test incrementally
