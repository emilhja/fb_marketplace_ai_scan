import logging
import os
import sys
from pathlib import Path

import psycopg

project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

# .env loader
env_file = project_root / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ[k] = v

from ai_marketplace_monitor.monitor import MarketplaceMonitor
from ai_marketplace_monitor.utils import CacheType, cache


def main():
    db_url = os.environ.get("AIMM_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        print("Error: AIMM_DATABASE_URL not found.")
        sys.exit(1)

    print("Connecting to DB...")
    kind_to_urls = {}
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT l.canonical_post_url, a.listing_kind
                FROM listings l
                LEFT JOIN ai_evaluations a ON l.id = a.listing_id
                WHERE l.user_feedback = 'down';
                """)
            for row in cur.fetchall():
                url = row[0]
                kind = row[1] or "unknown"
                if kind not in kind_to_urls:
                    kind_to_urls[kind] = []
                if url not in kind_to_urls[kind]:
                    kind_to_urls[kind].append(url)

    total_urls = sum(len(urls) for urls in kind_to_urls.values())
    if not total_urls:
        print("No listings with thumbs down feedback found in the database.")
        sys.exit(0)

    print(f"Found {total_urls} listings with thumbs down feedback.")

    cleared = 0
    for urls in kind_to_urls.values():
        for url in urls:
            clean_url = url.split("?")[0]
            cache_key = (CacheType.LISTING_DETAILS.value, clean_url)
            if cache.delete(cache_key):
                cleared += 1

    print(f"Successfully removed {cleared} items from diskcache.")

    logger = logging.getLogger("rescrape_thumbs_down")
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    monitor = MarketplaceMonitor(config_files=None, headless=False, logger=logger)
    try:
        monitor.load_config_file()
        expected_items = list(monitor.config.item.keys())

        for kind, urls in kind_to_urls.items():
            target_kind = kind
            if target_kind not in expected_items:
                if len(expected_items) == 1:
                    target_kind = expected_items[0]
                else:
                    print(f"Skipping URLs because kind is unknown/missing from config: {kind}")
                    print(urls)
                    continue

            print(f"Checking {len(urls)} items for config: {target_kind}...")
            for url in urls:
                try:
                    monitor.check_items(items=[url], for_item=target_kind)
                except Exception as e:
                    print(f"Skipping failed URL {url}: {e}")

    except Exception as e:
        print(f"Error during check_items: {e}")
    finally:
        monitor.stop_monitor()

    print("Done rescraping and evaluating thumbs down listings.")


if __name__ == "__main__":
    main()
