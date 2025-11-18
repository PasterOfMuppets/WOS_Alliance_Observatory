"""Custom SQLAlchemy types for proper timezone handling in SQLite."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import TypeDecorator, DateTime
import pytz


class TZDateTime(TypeDecorator):
    """
    DateTime type that ensures timezone info is preserved in SQLite.

    SQLite stores datetimes as text, and SQLAlchemy's DateTime(timezone=True)
    doesn't always preserve the timezone suffix. This custom type ensures
    all datetimes are stored with explicit timezone info (+00:00 for UTC).
    """
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convert Python datetime to database value."""
        if value is not None:
            # Ensure timezone-aware
            if value.tzinfo is None:
                value = pytz.UTC.localize(value)
            # For SQLite, return ISO format string with timezone
            if dialect.name == 'sqlite':
                return value.isoformat()
        return value

    def process_result_value(self, value, dialect):
        """Convert database value to Python datetime."""
        if value is not None and isinstance(value, str):
            # Parse ISO format string
            if '+' in value or 'Z' in value:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            else:
                # Legacy data without timezone - assume UTC
                dt = datetime.fromisoformat(value)
                return pytz.UTC.localize(dt)
        return value
