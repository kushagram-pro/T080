"""Create (or promote) an active administrator account.

Registration only creates pending faculty accounts, so the first admin must be made here.

Usage (from backend/, venv active):
    python -m scripts.create_admin --email admin@lnmiit.ac.in --name "Portal Admin"
The password is prompted for (or read from the ADMIN_PASSWORD env var).
"""
import argparse
import getpass
import os
import sys

from sqlalchemy import select

from app.database import SessionLocal
from app.models import User, UserRole, UserStatus
from app.security.hashing import hash_password


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    email = args.email.strip().lower()

    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    if len(password) < 8:
        print("Password must be at least 8 characters", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, full_name=args.name)
            db.add(user)
            action = "Created"
        else:
            action = "Promoted"
        user.full_name = args.name
        user.hashed_password = hash_password(password)
        user.role = UserRole.admin
        user.status = UserStatus.active
        user.rejection_reason = None
        db.commit()
        print(f"{action} admin {email} (id={user.id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
