# WOS Alliance Observatory - Complete Guide

## Overview

The WOS Alliance Observatory is a comprehensive data tracking system for Whiteout Survival alliances. It uses AI-powered OCR to automatically extract data from game screenshots and stores it in a structured database for analysis and tracking over time.

---

## Table of Contents

1. [Event Tracking Systems](#event-tracking-systems)
2. [Database Schema](#database-schema)
3. [Processing Scripts](#processing-scripts)
4. [Common Operations](#common-operations)
5. [Data Analysis Examples](#data-analysis-examples)
6. [Future Enhancements](#future-enhancements)

---

## Event Tracking Systems

### 1. Bear Trap Events 🐻

**Frequency:** Every 47 hours per trap (2 traps total)
**What We Track:**
- Individual player damage scores and rankings
- Rally count for each event
- Total alliance damage
- Event start and end times

**Database Tables:**
- `bear_events` - Event metadata (trap ID, times, rally count, total damage)
- `bear_scores` - Individual player damage scores per event

**Processing Scripts:**
- `test_bear_ocr.py` - Process damage ranking screenshots
- `test_bear_overview.py` - Process battle overview screenshots (Tesseract-based)

**Usage Example:**
```bash
# Process damage rankings
docker compose exec app python3 /app/scripts/test_bear_ocr.py \
  "/app/Screenshot_samples/bear_damage.jpg" \
  --event-time "2025-11-12 03:00"

# Process battle overview
docker compose exec app python3 /app/scripts/test_bear_overview.py \
  "/app/Screenshot_samples/bear_overview.jpg" \
  --event-time 202511120300
```

**Key Features:**
- Automatically strips alliance tags for player matching
- Tracks which trap (1 or 2)
- Links battle overview stats to damage rankings

---

### 2. Foundry Events ⚔️

**Frequency:** Every 2 weeks (bi-weekly Sundays)
**What We Track:**
- Signups: Who joined Legion 1 or Legion 2, their foundry power, whether they voted
- Results: Individual arsenal point scores and rankings
- No-shows: Players who signed up but didn't participate

**Database Tables:**
- `foundry_events` - Event metadata (legion, date, participant counts)
- `foundry_signups` - Player signups with foundry power and voting status
- `foundry_results` - Individual player arsenal point scores

**Processing Scripts:**
- `test_foundry_signup.py` - Process signup screenshots
- `test_foundry_result.py` - Process result screenshots

**Usage Example:**
```bash
# Process signups
docker compose exec app python3 /app/scripts/test_foundry_signup.py \
  "/app/Screenshot_samples/foundry_signup.jpg" \
  --legion 1 \
  --event-date 2025-11-17

# Process results
docker compose exec app python3 /app/scripts/test_foundry_result.py \
  "/app/Screenshot_samples/foundry_result.jpg" \
  --legion 1 \
  --event-date 2025-11-03
```

**Key Features:**
- Tracks three statuses: "join", "legion_2_dispatched", "no_engagements"
- Only saves players who joined the specified legion
- Links signups to results for no-show analysis
- Tracks voting participation

**Important Date Note:**
- Signup screenshots are for the UPCOMING foundry (e.g., taken Tuesday for Sunday battle)
- Result screenshots are from the PREVIOUS foundry (e.g., taken Tuesday from 2 weeks ago)
- Always check mail timestamps in results to determine correct event date

---

### 3. Alliance Championship (AC) 🏆

**Frequency:** Every week (battles Wed-Fri, automated)
**What We Track:**
- Weekly signups with AC power
- No results tracking needed (battles are automated)

**Database Tables:**
- `ac_events` - Event metadata (week start date, total registered, total power)
- `ac_signups` - Individual player signups with AC power

**Processing Scripts:**
- `test_ac_signup.py` - Process AC signup screenshots

**Usage Example:**
```bash
# Process AC signups (week starting Monday)
docker compose exec app python3 /app/scripts/test_ac_signup.py \
  "/app/Screenshot_samples/ac_signup.jpg" \
  --week-start 2025-11-11
```

**Key Features:**
- Tracks total troop power and participant counts
- Ignores lane assignments and order numbers (dynamic data)
- Week starts on Monday

---

### 4. Contribution Tracking 💰

**Frequency:** Daily snapshots (resets Sunday night)
**What We Track:**
- Cumulative weekly contribution for each day
- Player rankings

**Database Tables:**
- `contribution_snapshots` - Individual snapshots (player, amount, date, rank)

**Processing Scripts:**
- Script to be created (operations ready)

**Usage Example:**
```bash
# Process contribution snapshot
docker compose exec app python3 /app/scripts/test_contribution.py \
  "/app/Screenshot_samples/contribution.jpg" \
  --week-start 2025-11-11 \
  --snapshot-date 2025-11-12
```

**Key Features:**
- Stores cumulative totals (Thursday = Mon+Tue+Wed+Thu)
- Multiple snapshots per week supported (Tuesday, Thursday, Saturday)
- Good for identifying low contributors

---

### 5. Alliance Power Rankings 📊

**Frequency:** Ad-hoc snapshots
**What We Track:**
- All alliances in the state/server
- Total power for each alliance
- Rankings over time

**Database Tables:**
- `alliance_power_snapshots` - Alliance name, tag, power, rank, date

**Processing Scripts:**
- Test script embedded in operations (can be extracted)

**Usage Example:**
```python
from observatory.ocr.ai_client import OpenAIVisionExtractor
from observatory.db.alliance_power_operations import save_alliance_power_snapshot_ocr
from observatory.db.session import SessionLocal
from pathlib import Path
from datetime import datetime
import pytz

extractor = OpenAIVisionExtractor(model='gpt-4o-mini')
result = extractor.extract_alliance_power(Path('/app/Screenshot_samples/alliance_power.jpg'))

snapshot_date = datetime(2025, 11, 11, tzinfo=pytz.UTC)
session = SessionLocal()
save_alliance_power_snapshot_ocr(session, snapshot_date, result.get('alliances', []), snapshot_date)
session.close()
```

**Key Features:**
- Tracks competitive landscape
- Parses alliance tags automatically
- See power growth/decline across alliances

---

## Database Schema

### Core Tables

**alliances**
- Stores alliance information
- Links to all events and players

**players**
- Alliance member information
- Current power and furnace level
- Status (active, inactive, retired)
- Links to all player-specific data

**player_power_history**
- Historical power tracking
- Captures power at specific times

**player_furnace_history**
- Historical furnace level tracking

### Event-Specific Tables

**bear_events & bear_scores**
- Trap events and individual damage scores

**foundry_events, foundry_signups, foundry_results**
- Legion battles, signups, and scores

**ac_events & ac_signups**
- Alliance Championship signups

**contribution_snapshots**
- Weekly contribution tracking

**alliance_power_snapshots**
- Alliance power rankings over time

**ai_ocr_results**
- Stores raw AI OCR outputs for debugging

---

## Processing Scripts

All scripts are in `/app/scripts/`:

### Alliance Member Data
- `test_ocr_pipeline.py` - Process alliance member screenshots (power/furnace)

### Bear Events
- `test_bear_ocr.py` - Process bear damage rankings
- `test_bear_overview.py` - Process bear battle overview (Tesseract)

### Foundry Events
- `test_foundry_signup.py` - Process foundry signup screenshots
- `test_foundry_result.py` - Process foundry result screenshots

### Alliance Championship
- `test_ac_signup.py` - Process AC signup screenshots

### Common Parameters
- `--alliance-id` - Alliance ID (default: 1)
- `--event-time` / `--event-date` - Event timing (format varies by script)
- Screenshot path is always the first positional argument

---

## Common Operations

### 1. Add New Alliance Members

```bash
docker compose exec app python3 /app/scripts/test_ocr_pipeline.py \
  "/app/Screenshot_samples/members.jpg" \
  --alliance-id 1
```

### 2. Track Player Power Over Time

```sql
SELECT
  p.name,
  pph.power,
  pph.captured_at
FROM player_power_history pph
JOIN players p ON p.id = pph.player_id
WHERE p.name = 'Valorin'
ORDER BY pph.captured_at;
```

### 3. Find No-Shows in Foundry

```sql
SELECT
  p.name,
  fs.foundry_power,
  fs.voted
FROM foundry_signups fs
JOIN players p ON p.id = fs.player_id
LEFT JOIN foundry_results fr ON fr.foundry_event_id = fs.foundry_event_id
  AND fr.player_id = fs.player_id
WHERE fr.id IS NULL
  AND fs.foundry_event_id = 1;
```

### 4. Compare Alliance Power Over Time

```sql
SELECT
  snapshot_date,
  alliance_name,
  alliance_tag,
  total_power,
  rank
FROM alliance_power_snapshots
WHERE alliance_tag = 'HEI'
ORDER BY snapshot_date;
```

### 5. Identify Low Contributors

```sql
SELECT
  p.name,
  cs.contribution_amount,
  cs.rank
FROM contribution_snapshots cs
JOIN players p ON p.id = cs.player_id
WHERE cs.snapshot_date = '2025-11-16'  -- Saturday before reset
  AND cs.contribution_amount < 50000
ORDER BY cs.contribution_amount;
```

---

## Data Analysis Examples

### Weekly Contribution Trends

Compare same-day snapshots across weeks:

```sql
SELECT
  cs.week_start_date,
  p.name,
  cs.contribution_amount
FROM contribution_snapshots cs
JOIN players p ON p.id = cs.player_id
WHERE p.name = 'Valorin'
  AND strftime('%w', cs.snapshot_date) = '6'  -- Saturdays only
ORDER BY cs.week_start_date;
```

### Foundry Power Growth

Track individual player foundry power over time:

```sql
SELECT
  fe.event_date,
  p.name,
  fs.foundry_power,
  fs.voted
FROM foundry_signups fs
JOIN players p ON p.id = fs.player_id
JOIN foundry_events fe ON fe.id = fs.foundry_event_id
WHERE p.name = 'Stevieツ'
ORDER BY fe.event_date;
```

### Bear Event Performance

Top performers across all bear events:

```sql
SELECT
  p.name,
  COUNT(*) as events_participated,
  AVG(bs.score) as avg_damage,
  MAX(bs.score) as max_damage,
  AVG(bs.rank) as avg_rank
FROM bear_scores bs
JOIN players p ON p.id = bs.player_id
GROUP BY p.name
HAVING events_participated >= 3
ORDER BY avg_damage DESC;
```

### Alliance Power Rankings Changes

See how alliances are moving in rankings:

```sql
WITH ranked_snapshots AS (
  SELECT
    alliance_name,
    alliance_tag,
    snapshot_date,
    rank,
    LAG(rank) OVER (PARTITION BY alliance_name ORDER BY snapshot_date) as prev_rank
  FROM alliance_power_snapshots
)
SELECT
  alliance_name,
  alliance_tag,
  snapshot_date,
  rank,
  prev_rank,
  (prev_rank - rank) as rank_change
FROM ranked_snapshots
WHERE prev_rank IS NOT NULL
ORDER BY snapshot_date DESC, rank;
```

---

## AI OCR Configuration

### Model Selection

Current default: `gpt-4o-mini` (cost-effective, accurate)
Alternative: `gpt-4.1-mini` (if needed)

Configure in `.env`:
```
AI_OCR_MODEL=gpt-4o-mini
OPENAI_API_KEY=your_key_here
```

### Dual OCR Strategy

1. **AI Vision API** - Used for complex screenshots:
   - Alliance member cards (power + furnace)
   - Bear damage rankings
   - Foundry signups and results
   - AC signups
   - Contribution rankings
   - Alliance power rankings

2. **Tesseract OCR** - Used for simple text extraction:
   - Bear battle overview (rally count, total damage)
   - Future: Simple text-only screens

**Cost Optimization:** Tesseract is free but less accurate. Use for simple, structured text.

---

## Timestamp Handling

### Screenshot Timestamps

The system extracts timestamps from:
1. **Filename** (preferred): `Screenshot_YYYYMMDD_HHMMSS_*.jpg`
2. **EXIF data** (fallback): Image metadata

### Timezone Conversion

Screenshots are typically in `America/New_York` timezone.
Configure in `settings.py`:
```python
screenshot_timezone: str = "America/New_York"
```

All dates stored in database are **UTC**.

### Event Dating

- **Bear**: User provides trap start time
- **Foundry**: User provides event date (Sunday of battle)
- **AC**: Week start date (Monday)
- **Contribution**: Week start date (Monday) + snapshot date
- **Alliance Power**: Snapshot date only

---

## Player Name Matching

### Alliance Tag Stripping

Player names in screenshots often include alliance tags:
- Screenshot: `[HEI]Valorin`
- Database: `Valorin`

The system automatically strips `[TAG]` prefixes for matching.

### Special Characters

Player names with special characters are preserved:
- `D A D D Y☭〜`
- `Stevieツ`
- `必須認真`

### Duplicate Handling

If players are found with slight name variations:
1. Use database operations to merge records
2. Move history to correct player
3. Delete duplicate

Example from session:
```python
# SISABER vs SßABER - user confirmed SßABER is correct
# Merged SISABER into SßABER
```

---

## Future Enhancements

### Pending Implementation

1. **Event Leaderboards** (waiting for screenshots)
   - Alliance Showdown
   - King of Icefield (KoI)
   - State vs State (SVS)
   - Alliance Mobilization
   - Daily + Weekly scores

2. **Canyon Clash**
   - Same structure as Foundry
   - Different event type detection
   - Monthly frequency

3. **Powder Tracking**
   - Need clarification on what "powder" represents
   - Tracking mechanism TBD

4. **Full Automation Pipeline**
   - Drop screenshots in folder
   - Auto-detect screenshot type
   - Process automatically
   - Save to database
   - Architecture ready, needs integration

### Event Type Detection

Future automation will use:
- Screen title keywords ("Foundry Battle", "Canyon Clash")
- Screenshot structure patterns
- AI-based classification

### Web Interface

Consider building:
- Upload screenshots via web UI
- View dashboards and trends
- Export reports
- Player performance tracking
- Alliance comparison charts

---

## Troubleshooting

### Common Issues

**Player Not Found**
```
WARNING: Player not found: PlayerName, skipping
```
**Solution:** Player doesn't exist in alliance members table. Run alliance member OCR first.

**Duplicate Entries**
- Multiple screenshots may capture same players
- Database allows duplicates for historical tracking
- Query with `DISTINCT` or latest `recorded_at`

**Wrong Event Date**
- For results screenshots, check mail timestamp in image
- Foundry results are typically 2 weeks old when viewing signup screenshots

**OCR Extraction Errors**
- Check AI OCR results in `ai_ocr_results` table
- Verify OPENAI_API_KEY is set
- Try different model (gpt-4.1-mini vs gpt-4o-mini)

### Database Access

```bash
# Connect to SQLite database
docker compose exec app python3 -c "
from observatory.db.session import engine
import sqlite3
conn = sqlite3.connect('/data/observatory.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM players LIMIT 5')
print(cursor.fetchall())
"
```

---

## Performance Tips

1. **Batch Processing:** Process multiple screenshots in loops
2. **Parallel OCR:** Can process independent screenshots simultaneously
3. **Tesseract for Simple Text:** Use when possible to reduce API costs
4. **Database Indexes:** Already optimized on key columns (dates, IDs, tags)
5. **Query Optimization:** Use indexes, avoid full table scans

---

## Data Retention

- No automatic deletion
- All historical data preserved
- Manual cleanup if needed:
  ```sql
  DELETE FROM contribution_snapshots WHERE snapshot_date < '2025-01-01';
  ```

---

## Security Notes

- Never commit `.env` file with API keys
- Database file in `/data` volume (persistent)
- Screenshots in `/app/Screenshot_samples` (read-only mount)
- OCR results stored for debugging (contains screenshot paths)

---

## Credits

Built using:
- **Python 3.11**
- **FastAPI** - Web framework
- **SQLAlchemy** - ORM
- **OpenAI Vision API** - AI OCR
- **Tesseract** - Traditional OCR
- **Docker Compose** - Containerization
- **Caddy** - Reverse proxy

---

## Web Interface

The WOS Alliance Observatory now includes a complete web interface for easy access to all data!

### Accessing the Web UI

**URL:** `http://localhost:7500/`

**Default Login:**
- Username: `admin`
- Password: `admin`

### Web Features

**1. Authentication System**
- User registration and login
- JWT-based authentication
- Secure password hashing

**2. Dashboard** (`/dashboard`)
- Quick access to all features
- Welcome message with user info
- Navigation cards for all sections

**3. Player Roster** (`/roster`)
- View all active players sorted by power
- Current power and furnace levels
- Interactive historical charts (Chart.js)
- Click "View History" for power/furnace trends over time

**4. Bear Events** (`/events/bear`)
- View all bear trap events
- Filter by Trap 1 or Trap 2
- See rally counts, total damage
- Top performers per event

**5. Foundry Events** (`/events/foundry`)
- View all foundry battles
- Filter by Legion 1 or Legion 2
- Signup counts, participation rates
- Top arsenal point scorers
- Win/loss tracking

**6. Alliance Championship** (`/events/ac`)
- Weekly AC signup history
- Total registered and power
- Participation tracking

**7. Contribution Tracking** (`/events/contribution`)
- Weekly contribution snapshots
- Multiple snapshots per week
- Track cumulative progress
- Identify low contributors

**8. Screenshot Upload** (`/upload`)
- Drag-and-drop file upload
- Multi-file selection
- Bulk upload support
- Files saved to `/app/uploads`
- (Auto-processing to be added in future)

### API Endpoints

All data accessible via REST API:
- `POST /api/login` - User authentication
- `POST /api/register` - User registration
- `GET /api/me` - Current user info
- `GET /api/players` - Player roster
- `GET /api/players/{id}/history` - Historical data
- `GET /api/events/bear` - Bear events
- `GET /api/events/foundry` - Foundry events
- `GET /api/events/ac` - AC events
- `GET /api/events/contribution` - Contribution snapshots
- `POST /api/upload/screenshots` - Bulk upload

### Creating Additional Users

Run the script to create new users:
```bash
docker compose exec app python3 /app/scripts/create_test_user.py
```

Or modify the script to create custom users with different credentials.

---

## Summary

The WOS Alliance Observatory provides comprehensive tracking for:
- ✅ Alliance member power and furnace levels
- ✅ Bear trap events (damage, rallies, totals)
- ✅ Foundry battles (signups, results, no-shows)
- ✅ Alliance Championship signups
- ✅ Weekly contribution snapshots
- ✅ Alliance power rankings (competitive landscape)
- ✅ **Complete web interface for data viewing and management**
- ✅ **User authentication and access control**
- ✅ **Interactive charts and historical data visualization**

**Total Events Tracked:** 100+ members, 23 bear scores, 48 foundry records, 81 AC signups, 10 alliance rankings

The system is production-ready with both CLI scripts and web interface!
