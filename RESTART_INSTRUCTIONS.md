# WOS Observatory - Restart Instructions

## Quick Fix: Restart Container

The code changes are already in place, but the container needs to be restarted:

```bash
# Option 1: Restart just the app container (fastest)
docker compose restart app

# Option 2: Full restart (if Option 1 doesn't work)
docker compose down
docker compose up -d
```

After restarting, test the login endpoint:
```bash
curl -X POST http://localhost:7500/api/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=testuser&password=testpass"
```

---

## If Error Persists: Database Initialization

The error might be caused by a missing `users` table. Check and initialize:

### 1. Check Database Health
```bash
docker compose exec app bash /app/scripts/check_db_health.sh
```

### 2. Run Database Migrations (if needed)
```bash
# Run all pending migrations
docker compose exec app alembic upgrade head

# Verify migrations were applied
docker compose exec app alembic current
```

### 3. Create Test User (if table exists but no users)
```bash
docker compose exec app python3 -c "
from observatory.db.session import SessionLocal
from observatory.db.models import User
from observatory.auth import get_password_hash

session = SessionLocal()
try:
    # Create test user
    user = User(
        username='admin',
        email='admin@example.com',
        password_hash=get_password_hash('admin123'),
        is_active=True,
        is_admin=True
    )
    session.add(user)
    session.commit()
    print('✓ Test user created: admin / admin123')
except Exception as e:
    print(f'✗ Error: {e}')
    session.rollback()
finally:
    session.close()
"
```

---

## Debugging: View Container Logs

If the error still persists, check the logs for detailed error messages:

```bash
# View recent logs
docker compose logs app --tail=50

# Follow logs in real-time
docker compose logs app -f

# Check for specific error patterns
docker compose logs app | grep -i "error\|exception\|traceback"
```

---

## What Was Fixed

The login API 500 error was caused by **duplicate `get_session()` functions**:

- ✅ **Removed** duplicate from `app/src/observatory/auth.py`
- ✅ **Updated** all endpoints to use canonical `get_session` from `db.session`
- ✅ **Committed** and pushed to branch: `claude/fix-login-api-error-01QnpokUF5okwUsLLC4jSJbs`

**Changes are live on disk** (via mounted volume), but container restart is required.

---

## Still Having Issues?

Run the full diagnostic:
```bash
# 1. Check container status
docker compose ps

# 2. Check database health
docker compose exec app bash /app/scripts/check_db_health.sh

# 3. Test API health
curl http://localhost:7500/health

# 4. Test database connectivity
curl http://localhost:7500/db/health

# 5. View full logs
docker compose logs app --tail=100
```

If the issue persists, please share:
1. Output from `docker compose logs app --tail=50`
2. Output from the database health check
3. Any specific error messages from the browser console
