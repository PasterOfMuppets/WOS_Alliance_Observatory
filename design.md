# WOS Alliance Observatory — System Design Document
# Whiteout Survival Alliance Tracker — System Design Document

## 1. Overview & Goals

This system will track Whiteout Survival alliance members' statistics by processing in-game screenshots using OCR. It will support:

- Extracting player names, power, furnace level, and event-specific stats.
- Tracking changes over time.
- Supporting multiple alliances.
- Allowing uploads of screenshots by authorized users.
- Displaying data via a lightweight web interface.

The system is designed for **minimal load**:
- ~5 upload-capable users
- Upload frequency: 1–2 times per week
- ~10 viewers accessing data a few times per week

The design prioritizes *simplicity, low cost, extensibility,* and *containerization*.

---

## 2. High-Level Architecture

### Components

#### **2.1 OCR Processing Module**
- Local OCR using **Tesseract**.
- Detects screenshot type by keywords/layout:
  - Alliance Members list
  - Alliance Contribution
  - Alliance Championship lanes
  - Event rankings (SvS, King of Icefield, etc.)
- Extracts structured data:
  - Player name
  - Power
  - Furnace level
  - Contribution score
  - Event-specific values

#### **2.2 Database Layer**
- **SQLite** for Phase 1.
- Accessed via an ORM (e.g., SQLAlchemy) to preserve portability.
- Schema includes:
  - Alliances
  - Players
  - Player Stats (power, furnace, etc.)
  - Event Stats (per event type)
  - Users
  - Roles
  - User ↔ Alliance permissions

#### **2.3 Web Application**
- Built with **Flask** (lightweight, familiar, easy to containerize).
- Provides:
  - Login & authentication
  - Role-based access control
  - Alliance selection (based on permissions)
  - Data views:
    - Player power history
    - Contributions
    - Event results
    - Rosters

#### **2.4 Upload Interface**
- Web form for screenshot upload.
- Validates image type.
- Sends to OCR module.
- Stores extracted data into DB.

---

## 3. Multi-Alliance Support

The system must support multiple alliances.

### Requirements:
- Each alliance has separate players, stats, and events.
- Users have **permissions per alliance**:
  - Viewer may access one, several, or all alliances.
  - Uploaders may upload for specific alliances.
  - Admin can manage alliances, members, and users.

### Data Model Implications:
- Player table includes `alliance_id`.
- Stats tables reference `player_id` + timestamps.
- User permissions stored in a linking table:
  - `user_alliance_permissions(user_id, alliance_id, role)`.

---

## 4. User Roles & Access Control

### **Admin**
- Full control.
- Manage alliances.
- Manage users.
- Assign viewer/uploader permissions.
- View all data.
- Upload screenshots for any alliance.

### **Uploader**
- Can upload screenshots for alliances they have permission for.
- Cannot manage users or alliances.

### **Viewer**
- Read-only access.
- Can view stats for assigned alliances only.

---

## 5. Screenshot Processing Flow

### Phase 1 (Local Directory Processing)
1. User drops images into `/screenshots/inbox`.
2. Processor scans directory.
3. OCR module detects screenshot type.
4. Extracted data is parsed and validated.
5. DB is updated.
6. Image is moved to `/screenshots/processed` (or deleted in production).
7. Logs are updated.

### Phase 3 (Web Upload)
1. Authenticated uploader selects alliance.
2. Uploads one or more screenshots.
3. Server processes images and updates DB.
4. Results displayed back to user.

---

## 6. Database Schema (Initial Draft)

### **alliances**
- id (PK)
- name

### **players**
- id (PK)
- alliance_id (FK)
- name
- current_power
- current_furnace
- status (optional: online/offline)

### **player_power_history**
- id
- player_id (FK)
- power
- timestamp

### **player_furnace_history**
- id
- player_id (FK)
- furnace_level
- timestamp

### **event_stats**
- id
- player_id (FK)
- event_type
- value
- date
- timestamp

(Event types include: Contribution, Alliance Championship power, SvS, KoI, etc.)

### **users**
- id
- username
- password_hash

### **user_roles**
- id
- user_id
- role (admin, uploader, viewer)

### **user_alliance_permissions**
- id
- user_id
- alliance_id
- role_for_alliance (uploader/viewer)

---

## 7. Containerization Plan (Docker)

### Container Layout

/app
OCR container (Tesseract + Python scripts)
Web container (Flask backend + API)
Frontend container (optional, or served by Flask)
Database container (optional: SQLite usually stored on host)

### Notes:
- SQLite typically runs on the host or in the web container.
- OCR container communicates with the web container via internal network.
- The entire stack defined via `docker-compose.yml`.

---

## 8. Hosting & Cost Considerations

### Priorities:
- Free / minimal-cost hosting.
- Lightweight containers.
- SQLite for now (upgradeable later).
- Screenshots **not** stored in production (only processed).

### Options:
- Backend: Fly.io / Railway free tier / small VPS / local execution.
- Frontend: Netlify (free tier).
- Authentication via Flask login or Authlib.

---

## 9. Future Enhancements (Planned)

- Add player inactivity detection (based on missing screenshots).
- Add charts/graphs (e.g., via Chart.js).
- Push notifications for weekly events.
- Support scheduled batch OCR on upload.
- Switch to PostgreSQL if data grows.
- Add alliance comparison dashboards.

---

## 10. Next Steps

1. Build `docker-compose.yml` framework.
2. Create basic Flask app + login system.
3. Implement SQLite schema.
4. Write OCR classifier for screenshot types.
5. Write extraction functions for:
   - Alliance roster screenshots
   - Contribution screenshots
   - Alliance Championship lane screenshots
   - Event ranking screenshots
6. Integrate upload endpoint.
7. Add web dashboards.

---

