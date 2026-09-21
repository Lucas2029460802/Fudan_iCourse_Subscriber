"""Dump all course summaries from the database into per-course folders.

Usage:
    python scripts/publish_overview.py --db data/icourse.db --out overview
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.database import Database  # noqa: E402
from src.api.overview import dump_from_db  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Write course summaries as Markdown, one folder per course.",
    )
    parser.add_argument(
        "--db", default="data/icourse.db",
        help="Database path (default: data/icourse.db)",
    )
    parser.add_argument(
        "--out", default="overview",
        help="Output directory (default: overview)",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.db):
        print(f"Database not found: {args.db}")
        sys.exit(1)

    db = Database(args.db)
    n_courses, n_files = dump_from_db(db, args.out)
    print(f"Wrote {n_files} lecture file(s) across {n_courses} course folder(s) "
          f"to {args.out}/")


if __name__ == "__main__":
    main()
