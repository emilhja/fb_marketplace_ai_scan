#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ai_marketplace_monitor.pg_cache import prune_old_records


def main() -> int:
    parser = argparse.ArgumentParser(description="Prune old PostgreSQL cache records.")
    parser.add_argument(
        "--retention-days",
        type=int,
        default=int((os.environ.get("AIMM_DB_RETENTION_DAYS") or "60").strip()),
        help="Keep records newer than this many days (default: 60 or AIMM_DB_RETENTION_DAYS).",
    )
    args = parser.parse_args()
    deleted = prune_old_records(args.retention_days)
    print(
        "Pruned records:",
        f"ai_evaluations={deleted['ai_evaluations']}",
        f"listing_price_history={deleted['listing_price_history']}",
        f"notification_events={deleted['notification_events']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
