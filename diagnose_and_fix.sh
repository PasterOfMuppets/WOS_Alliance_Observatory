#!/bin/bash
# Complete diagnostic and fix script for login API error

set -e

echo "=========================================="
echo "WOS Observatory - Login Fix Diagnostic"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Check container status
echo -e "${YELLOW}Step 1: Checking container status...${NC}"
if ! docker compose ps | grep -q "wos_app.*Up"; then
    echo -e "${RED}✗ App container is not running${NC}"
    echo "Starting containers..."
    docker compose up -d
    sleep 5
else
    echo -e "${GREEN}✓ App container is running${NC}"
fi
echo ""

# Step 2: Restart container to pick up code changes
echo -e "${YELLOW}Step 2: Restarting app container to pick up code changes...${NC}"
docker compose restart app
echo "Waiting for app to start..."
sleep 5
echo -e "${GREEN}✓ Container restarted${NC}"
echo ""

# Step 3: Check app logs for errors
echo -e "${YELLOW}Step 3: Checking recent application logs...${NC}"
echo "----------------------------------------"
docker compose logs app --tail=30
echo "----------------------------------------"
echo ""

# Step 4: Test basic endpoints
echo -e "${YELLOW}Step 4: Testing basic endpoints...${NC}"

# Test health endpoint
if curl -s http://localhost:7500/health | grep -q "ok\|degraded"; then
    echo -e "${GREEN}✓ Health endpoint working${NC}"
else
    echo -e "${RED}✗ Health endpoint not responding${NC}"
fi

# Test database health
if curl -s http://localhost:7500/db/health | grep -q "ok"; then
    echo -e "${GREEN}✓ Database connection working${NC}"
else
    echo -e "${RED}✗ Database connection failed${NC}"
fi
echo ""

# Step 5: Check database schema
echo -e "${YELLOW}Step 5: Checking database schema...${NC}"
docker compose exec -T app sqlite3 /data/observatory.db <<'SQL'
.tables
SQL

if docker compose exec -T app sqlite3 /data/observatory.db "SELECT name FROM sqlite_master WHERE type='table' AND name='users';" | grep -q users; then
    echo -e "${GREEN}✓ users table exists${NC}"
    USER_COUNT=$(docker compose exec -T app sqlite3 /data/observatory.db "SELECT COUNT(*) FROM users;")
    echo "  User count: $USER_COUNT"

    if [ "$USER_COUNT" -eq 0 ]; then
        echo -e "${YELLOW}⚠ No users in database${NC}"
        echo ""
        echo "Creating test user (admin/admin123)..."
        docker compose exec -T app python3 <<'PYTHON'
import sys
sys.path.insert(0, '/app/src')
from observatory.db.session import SessionLocal
from observatory.db.models import User
from observatory.auth import get_password_hash

session = SessionLocal()
try:
    # Check if user exists
    from sqlalchemy import select
    stmt = select(User).where(User.username == 'admin')
    existing = session.execute(stmt).scalar_one_or_none()

    if existing:
        print("User 'admin' already exists")
    else:
        user = User(
            username='admin',
            email='admin@example.com',
            password_hash=get_password_hash('admin123'),
            is_active=True,
            is_admin=True
        )
        session.add(user)
        session.commit()
        print("✓ Test user created: admin / admin123")
except Exception as e:
    print(f"✗ Error creating user: {e}")
    session.rollback()
finally:
    session.close()
PYTHON
    fi
else
    echo -e "${RED}✗ users table NOT found${NC}"
    echo ""
    echo "Running database migrations..."
    docker compose exec app alembic upgrade head
    echo ""
    echo "Please run this script again after migrations complete."
    exit 1
fi
echo ""

# Step 6: Test login endpoint
echo -e "${YELLOW}Step 6: Testing login endpoint...${NC}"
echo "Attempting login with admin/admin123..."
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST http://localhost:7500/api/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin123")

HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
BODY=$(echo "$RESPONSE" | sed '$d')  # Remove last line (portable for macOS/Linux)

if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✓✓✓ Login successful! ${NC}"
    echo "Response:"
    echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
    echo ""
    echo -e "${GREEN}=========================================="
    echo "Login API is now working correctly!"
    echo "==========================================${NC}"
elif [ "$HTTP_CODE" -eq 401 ]; then
    echo -e "${YELLOW}⚠ Login returned 401 (credentials incorrect or user doesn't exist)${NC}"
    echo "Response: $BODY"
    echo ""
    echo "Try creating a user first or check credentials."
elif [ "$HTTP_CODE" -eq 500 ]; then
    echo -e "${RED}✗ Login still returning 500 error${NC}"
    echo "Response: $BODY"
    echo ""
    echo "Checking detailed logs..."
    echo "----------------------------------------"
    docker compose logs app --tail=20 | grep -i "error\|exception\|traceback"
    echo "----------------------------------------"
    echo ""
    echo "Possible issues:"
    echo "1. Import error in the application"
    echo "2. Database connection issue"
    echo "3. Missing dependencies"
    echo ""
    echo "Run: docker compose logs app --tail=100"
    echo "Look for the actual Python traceback."
else
    echo -e "${RED}✗ Unexpected HTTP code: $HTTP_CODE${NC}"
    echo "Response: $BODY"
fi
echo ""
