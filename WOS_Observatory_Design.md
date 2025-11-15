# **WOS Alliance Observatory — Design Document (v2)**  
*Updated to include Bear events, rename recycling, OCR strategy, improved schema, and structural additions.*

---

## **1. Project Overview**

The **WOS Alliance Observatory** is a containerized web system that extracts player and event data from uploaded Whiteout Survival screenshots and stores structured historical data for multiple alliances.

The system will:

- Track player power, furnace level, contribution, bear scores, lane assignments, and other event activity  
- Maintain historical timelines  
- Support multiple alliances  
- Provide role-based access (admin, uploader, viewer)  
- Offer a simple upload interface with automatic OCR  
- Display dashboards for alliance leaders and players  

It must run inexpensively, with low compute requirements.

---

## **2. Key Features**

- OCR-based extraction from game screenshots  
- Screenshot type classifier  
- Multi-alliance database design  
- Roles: admin, uploader, viewer  
- Historical tracking:  
  - Power  
  - Furnace  
  - Weekly Contribution  
  - Alliance Championship lanes  
  - **Bear events (Bear 1 & Bear 2)**  
- Player identity resolution with rename handling and alias tracking  
- Full containerization  
- SQLite initially, modular for Postgres  
- Upload queue + error reporting  
- Admin tools (merge players, edit OCR errors)

---

## **3. Supported Screenshot Types (Phase 1)**

### **3.1 Alliance Members List**
Extract:
- Player name  
- Power  
- Furnace level  
- Online status (optional)

Detection markers:
- “Alliance Members”
- “Online: X/100”

---

### **3.2 Alliance Contribution Rankings**
Extract:
- Player name  
- Weekly contribution  
- Ranking  

Markers:
- “Alliance Ranking”
- “Contribution Rankings”
- “Weekly Contribution”

---

### **3.3 Alliance Championship Lanes**
Extract:
- Lane (Left / Middle / Right)  
- Order of battle  
- Player name  
- AC Power  

Markers:
- Lane tabs  
- “Registered:”  
- “Power:”

---

### **3.4 Bear Event Screens (NEW)**

The alliance has **two Bear traps**:
- **Bear 1**
- **Bear 2**

Each trap:
- Runs independently  
- Has a **minimum 47-hour cooldown**  
- Occurs at variable times  

Extract:
- Trap ID (Bear 1 / Bear 2)  
- Player name  
- Player score  
- Rank  

Markers:
- “Bear”
- “Bear 1” or “Bear 2”
- Scores typically numeric with comma separators

System must store **all Bear history** permanently.

---

### **3.5 Additional Types (Future)**
- State vs State (SvS)  
- King of Icefield (KoI)  
- Alliance Mobilization  

Each will require a specific parser.

---

## **4. OCR Strategy**

### **4.1 Detection (“Coarse Pass”)**
- Downscale screenshot (~600px width)  
- Extract text across entire image  
- Look for distinct keywords to identify screenshot type  
- If none found → mark screenshot as *failed*

---

### **4.2 Region-Based Extraction (“Fine Pass”)**
Once type is known, crop fixed regions based on device resolution:

- Name region  
- Power  
- Furnace  
- Contribution  
- Lane power  
- Bear score region  

OCR these small boxes individually for higher accuracy.

---

### **4.3 Preprocessing**
- Convert to grayscale  
- Light Gaussian blur  
- Adaptive threshold  
- Upscale numeric regions (1.2–1.5x)  
- Otsu binarization for text clarity

---

### **4.4 Parsing Methods**
- **Names** → text between avatar and label  
- **Power** → `([\d,]+(\.\d+)?M?)`  
- **Contribution** → numeric  
- **Bear score** → numeric  
- **Rank** → integer  

Low-confidence results → flagged for admin review.

---

## **5. Player Identity Resolution**

### **5.1 WOS Name Rules (Important)**
- Players **can rename**  
- Names can be **reused** after abandoned  
- Two players can use same name, sequentially  
- Unique player ID exists, but only visible on one screen  
- OCR inaccuracies may produce near-duplicate names

---

### **5.2 Resolution Flow**
1. OCR extracts name  
2. Try **exact match** in `player_aliases`  
3. If not found → try **fuzzy match** (Levenshtein ≤ 2)  
4. If still not found → create **new player**  
5. When unique player ID is available (rare):  
   - Permanently bind aliases to that player  
6. Admin UI allows merging mistaken duplicates  

---

### **5.3 Data Structures**

```sql
players (
  id INTEGER PRIMARY KEY,
  alliance_id INTEGER,
  created_at DATETIME
);

player_aliases (
  id INTEGER PRIMARY KEY,
  player_id INTEGER,
  alliance_id INTEGER,
  name_text TEXT,
  first_seen_at DATETIME,
  last_seen_at DATETIME,
  confidence REAL
);
```

---

## **6. Bear Event Data Model (NEW)**

### **6.1 Bear Event Table**

```sql
bear_events (
  id INTEGER PRIMARY KEY,
  alliance_id INTEGER,
  trap_id INTEGER,        -- 1 or 2
  started_at DATETIME,
  ended_at DATETIME,
  created_at DATETIME
);
```

Each Bear trap run is a *new event*.

---

### **6.2 Bear Scores Table**

```sql
bear_scores (
  id INTEGER PRIMARY KEY,
  bear_event_id INTEGER,
  player_id INTEGER,
  score INTEGER,
  rank INTEGER,
  recorded_at DATETIME
);
```

Tracks **all history**, never overwritten.

---

## **7. Database Schema (Condensed)**

### **7.1 Player Status**

```sql
player_power_history (
  id,
  player_id,
  power_value,
  measured_at
);

player_furnace_history (
  id,
  player_id,
  furnace_level,
  measured_at
);
```

### **7.2 Contribution**

```sql
contribution_history (
  id,
  player_id,
  week_start_date,
  contribution_value,
  recorded_at
);
```

### **7.3 Alliance Championship (AC lanes)**

```sql
lane_results (
  id,
  alliance_id,
  lane TEXT,
  order_number INTEGER,
  player_id INTEGER,
  ac_power INTEGER,
  recorded_at DATETIME
);
```

### **7.4 Bear Events**

```sql
bear_events (...);
bear_scores (...);
```

### **7.5 Screenshot Tracking**

```sql
screenshots (
  id,
  alliance_id,
  uploader_id,
  filename,
  detected_type,
  status,
  error_message,
  uploaded_at,
  processed_at
);
```

---

## **8. Upload Workflow**

1. Uploader selects alliance  
2. Uploads 1–20 images  
3. Backend creates `screenshots` rows (status = pending)  
4. OCR worker processes  
5. If successful → status = success  
6. If failed → status = failed + error message  
7. UI shows:
   - X succeeded  
   - Y failed (with review links)

Store:
- uploader ID  
- upload timestamp  
- filename  
- detected type  
- results  

---

## **9. Security**

- Role-based auth (admin, uploader, viewer)  
- bcrypt or argon2 password hashing  
- HTTPS required for production  
- Accept only PNG/JPG  
- Max upload 5MB  
- Screenshots deleted after success  

---

## **10. UI / UX Overview**

### **10.1 Navigation**
- Alliance selector  
- Overview  
- Players  
- Contribution  
- Bear Events  
- Alliance Championship  
- Admin Tools  

---

### **10.2 Screens**
#### **Overview**
- Recent uploads  
- Top 10 power  
- Recent Bear events  

#### **Players**
- Table + search  
- Player profile with:
  - Power graph  
  - Furnace history  
  - Bear history  
  - Contribution timeline  

#### **Bear**
- Trap 1 / Trap 2  
- Historical runs  
- Leaderboards  

#### **Contribution**
- Weekly leaderboard  
- Trend lines  

#### **AC Lanes**
- Lanes for each battle  
- AC power trending  

---

## **11. Error Handling & Logging**

- Log uploads, OCR errors, merges  
- Screenshot failures in “Review OCR Issues” page  
- Log levels: INFO, WARN, ERROR  
- Daily SQLite backups  

---

## **12. Deployment**

Docker Compose stack:

```text
backend (FastAPI)
ocr worker
frontend (React/Svelte)
sqlite volume
reverse proxy (Traefik/Caddy)
```

- Automated DB backup  
- Optional migration to Postgres later  

---

## **13. Roadmap**

### **Phase 1 — Core**
- OCR for alliance members, contribution, AC lanes  
- DB schema  
- Basic UI  
- Player alias system  

### **Phase 2 — Bear**
- Bear OCR  
- Bear history  
- Bear dashboards  

### **Phase 3 — Advanced Events**
- SvS  
- KoI  
- Mobilization  
- Reporting suite  

---

# **End of Document**
