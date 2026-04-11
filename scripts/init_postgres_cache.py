#!/usr/bin/env python3
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from ai_marketplace_monitor.pg_cache import cache_enabled, ensure_database


def main() -> int:
    if not cache_enabled():
        return 0
    ok = ensure_database()
    if not ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
