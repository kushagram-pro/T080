"""Send the weekly email digest to every faculty member who is due one.

Safe to run as often as you like: each person gets at most one digest a week, and only when
there is something to tell them (pending requests, unread messages or new matching colleagues).
Schedule it weekly, e.g. Windows Task Scheduler running, from backend/:
    venv\\Scripts\\python.exe -m scripts.send_digest

Usage (from backend/, venv active):
    python -m scripts.send_digest            # send
    python -m scripts.send_digest --dry-run  # only log who would get one
"""
import argparse
import logging
import sys

from app.database import SessionLocal
from app.services.digest import send_due


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="log who would get a digest, send nothing")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with SessionLocal() as db:
        sent, skipped = send_due(db, dry_run=args.dry_run)
    verb = "Would send" if args.dry_run else "Sent"
    print(f"{verb} {sent} digest(s); {skipped} faculty had nothing new.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
