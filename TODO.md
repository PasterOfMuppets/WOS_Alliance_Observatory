# TODO List

## Data Persistence & Timestamp Handling

### Completed ✅
- ✅ Create data persistence layer to save parsed OCR results to database
- ✅ Implement player upsert logic (find or create player by name + alliance)
- ✅ Add power history record creation with captured_at timestamp
- ✅ Add furnace history record creation with captured_at timestamp
- ✅ Add SCREENSHOT_TIMEZONE config setting (default: America/New_York)
- ✅ Implement screenshot timestamp extraction (filename parser + EXIF fallback)
  - Filename format: `Screenshot_YYYYMMDD_HHMMSS_Whiteout Survival.jpg`
  - EXIF fallback if filename parsing fails
- ✅ Convert screenshot timestamp from configured timezone to UTC for storage
- ✅ Add created_at field to history tables to track DB insert time (separate from captured_at)
- ✅ Test full pipeline: OCR → Parse → Save → Query history
- ✅ Verify timestamps are correctly converted and stored in UTC

### In Progress
- [ ] Process all alliance member screenshots to build complete power history

### Future Work
- [ ] Web upload interface: design timezone handling
  - Auto-detect timezone from browser
  - Manual timezone override per upload
  - User profile setting for timezone preference

## AI OCR Improvements

### Completed ✅
- ✅ Fixed OpenAI API client (was using incorrect `responses.create()` endpoint)
- ✅ Updated to use `chat.completions.create()` for vision requests
- ✅ Implemented furnace level logic (FC1-FC9 for single digits, 25-30 for non-FC)
- ✅ Changed default model to gpt-4o-mini (cheaper, working well)
- ✅ Alliance Members OCR working correctly with proper furnace level detection

### Planned
- [ ] Extend AI OCR to handle all screenshot types:
  - [ ] Contribution Rankings
  - [ ] Alliance Championship (AC) Lanes
  - [ ] Bear Events (Bear 1 & Bear 2)
- [ ] Create type-specific prompts for each screenshot type
- [ ] Handle all 100 alliance players for complete roster tracking

## Database & Schema

### Issues to Fix
- [ ] Fix Alembic migrations not running automatically
  - Current workaround: manually create tables via SQLAlchemy
  - Need to investigate why `alembic upgrade head` doesn't initialize empty DB
- [ ] Implement player_aliases table (described in design docs but not in current schema)
  - Support player renames
  - Fuzzy name matching
  - Alias tracking with first_seen/last_seen timestamps

## Notes
- Screenshots are taken in EST timezone
- EXIF data typically stores local time without timezone info
- Database should store all timestamps in UTC for consistency
- Power/furnace levels should use screenshot timestamp (captured_at), not processing time
