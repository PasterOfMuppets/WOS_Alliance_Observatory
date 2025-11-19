#!/bin/bash
# Database health check script

set -e

echo "=== WOS Observatory Database Health Check ==="
echo ""

# Check if database exists
if [ -f /data/observatory.db ]; then
    echo "✓ Database file exists: /data/observatory.db"
else
    echo "✗ Database file NOT found: /data/observatory.db"
    echo "  → Run: docker compose exec app alembic upgrade head"
    exit 1
fi

echo ""
echo "=== Checking Database Tables ==="

# Check for users table
if sqlite3 /data/observatory.db "SELECT name FROM sqlite_master WHERE type='table' AND name='users';" | grep -q users; then
    echo "✓ users table exists"
    USER_COUNT=$(sqlite3 /data/observatory.db "SELECT COUNT(*) FROM users;")
    echo "  → User count: $USER_COUNT"
else
    echo "✗ users table NOT found"
    echo "  → Run migrations: docker compose exec app alembic upgrade head"
    exit 1
fi

# Check for other critical tables
for table in alliances players screenshots; do
    if sqlite3 /data/observatory.db "SELECT name FROM sqlite_master WHERE type='table' AND name='$table';" | grep -q $table; then
        echo "✓ $table table exists"
    else
        echo "✗ $table table NOT found"
    fi
done

echo ""
echo "=== Database Health Check Complete ==="
