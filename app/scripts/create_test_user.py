"""Create a test user for web UI login."""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from observatory.auth import get_password_hash
from observatory.db import models
from observatory.db.session import SessionLocal


def create_test_user():
    """Create a test user with username 'admin' and password 'admin'."""
    session = SessionLocal()

    try:
        # Check if user already exists
        existing_user = session.query(models.User).filter_by(username="admin").first()

        if existing_user:
            print("User 'admin' already exists!")
            return

        # Create new user
        hashed_password = get_password_hash("admin")
        new_user = models.User(
            username="admin",
            email="admin@example.com",
            password_hash=hashed_password,
            is_active=True,
            is_admin=True,
            default_alliance_id=1  # Assuming alliance ID 1 exists
        )

        session.add(new_user)
        session.commit()

        print("✓ Created test user:")
        print("  Username: admin")
        print("  Password: admin")
        print("  Email: admin@example.com")
        print("  Is Admin: Yes")
        print("  Default Alliance ID: 1")

    except Exception as e:
        print(f"Error creating user: {e}")
        session.rollback()
    finally:
        session.close()


if __name__ == "__main__":
    create_test_user()
