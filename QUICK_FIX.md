# Login 500 Error - Quick Fix Guide

## The Problem
You're getting `POST http://localhost:7500/api/login 500 (Internal Server Error)`

## Most Likely Cause
**The container hasn't restarted to pick up the code changes.**

---

## Solution 1: Restart Container (90% of cases)

```bash
# Quick restart
docker compose restart app

# Wait 5 seconds, then try logging in again
```

**If this doesn't work, proceed to Solution 2.**

---

## Solution 2: Run Complete Diagnostic

I've created a comprehensive diagnostic script that will:
- ✅ Restart the container
- ✅ Check database initialization
- ✅ Create a test user if needed
- ✅ Test the login endpoint
- ✅ Show detailed error logs

**Run this:**
```bash
./diagnose_and_fix.sh
```

---

## Solution 3: Manual Step-by-Step

If the script doesn't work, try these steps:

### Step 1: Check logs for actual error
```bash
docker compose logs app --tail=50 | grep -A 10 "POST /api/login"
```

Look for a Python traceback that shows the real error.

### Step 2: Verify database is initialized
```bash
docker compose exec app sqlite3 /data/observatory.db "SELECT name FROM sqlite_master WHERE type='table';"
```

You should see: `users`, `alliances`, `players`, etc.

**If users table is missing:**
```bash
docker compose exec app alembic upgrade head
```

### Step 3: Check if any users exist
```bash
docker compose exec app sqlite3 /data/observatory.db "SELECT username FROM users;"
```

**If no users exist, create one:**
```bash
docker compose exec app python3 -c "
import sys
sys.path.insert(0, '/app/src')
from observatory.db.session import SessionLocal
from observatory.db.models import User
from observatory.auth import get_password_hash

session = SessionLocal()
user = User(
    username='admin',
    email='admin@example.com',
    password_hash=get_password_hash('admin123'),
    is_active=True,
    is_admin=True
)
session.add(user)
session.commit()
session.close()
print('User created: admin/admin123')
"
```

### Step 4: Test login
```bash
curl -X POST http://localhost:7500/api/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123"
```

Expected: `{"access_token":"...","token_type":"bearer"}`

---

## What Was Fixed

The code fix removed duplicate `get_session()` functions:
- ✅ `app/src/observatory/auth.py` - removed duplicate, now imports from `db.session`
- ✅ `app/src/observatory/api.py` - all endpoints now use canonical `get_session`

**The fix is already on disk** (via mounted volume at `/app/src`), but:
- FastAPI/Uvicorn needs a **restart** to reload Python modules
- The database needs to be **initialized** with migrations
- At least **one user must exist** to test login

---

## Still Not Working?

Run the diagnostic and send me the output:
```bash
./diagnose_and_fix.sh > diagnostic_output.txt 2>&1
cat diagnostic_output.txt
```

Or check logs manually:
```bash
# Get full logs with traceback
docker compose logs app --tail=100 > app_logs.txt
cat app_logs.txt
```

Look for:
- Import errors
- Database connection errors
- "ModuleNotFoundError"
- "AttributeError"
- Any Python tracebacks

Share those specific error messages and I can help further!
