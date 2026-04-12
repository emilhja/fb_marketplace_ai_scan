# Facebook Marketplace scan

Hard fork of [ai-marketplace-monitor](https://pypi.org/project/ai-marketplace-monitor/) with local enhancements. `./run.sh` loads `.env`, activates `.venv`, initializes PostgreSQL cache tables, and runs the vendored local package via `python -m ai_marketplace_monitor.cli`. Configure searches in `~/.ai-marketplace-monitor/config.toml` (upstream config format is preserved).

## PostgreSQL dedupe and price-aware reprocessing

The wrapper can persist listing sightings, AI evaluations, and notification events in PostgreSQL to avoid repeated AI calls for unchanged listings.

### Setup

1. Install deps:
  ```bash
   pip install -r requirements.txt
  ```
2. Copy `.env.example` to `.env` and set at least:
  ```bash
   AIMM_DATABASE_URL=postgresql://user:pass@localhost:5432/marketplace_scan
   AIMM_PG_CACHE_ENABLED=1
   AIMM_REEVAL_ON_PRICE_CHANGE=1
   AIMM_REEVAL_ON_CONTENT_CHANGE=1
   AIMM_AI_REEVAL_COOLDOWN_MINUTES=0
   AIMM_PROMPT_VERSION=v1
  ```
3. Start normally with `./run.sh`.

`run.sh` exports the repo root to `PYTHONPATH`, initializes DB tables via `scripts/init_postgres_cache.py`, and then starts the local fork entrypoint.

### Behavior

- If listing price/content and prompt version/hash are unchanged, PostgreSQL cache is reused and AI is skipped.
- If price or content changed (policy-controlled), AI is re-run and the new result is stored.
- AI cache lookup key includes listing identity, model, item/marketplace config hashes, prompt version/hash, and price-aware/content-aware invalidation policy.
- Listing identity uses `marketplace + Facebook item ID` from URL when possible, with normalized URL hash fallback.
- DB logs include `ai_cache_hit`, `ai_cache_miss`, `ai_eval_persisted`, and persisted notification event entries.

### Maintenance

- Retention cleanup command:
  ```bash
  python3 scripts/pg_cache_maintenance.py --retention-days 60
  ```
- You can set default retention with `AIMM_DB_RETENTION_DAYS`.
- Schema bootstrap runs automatically from `scripts/init_postgres_cache.py` on each `./run.sh`.

### Upgrading this fork from upstream

1. Diff your forked package (`ai_marketplace_monitor/`) against upstream release notes.
2. Re-apply local features in these files first: `ai.py`, `monitor.py`, `facebook.py`, `pg_cache.py`.
3. Run tests (`python3 -m unittest discover -s tests`) and a dry scan before production use.

## Skipped listings, logs, and detail cache

When Facebook search filters out a listing (e.g. `[Skip] … without required keywords in title and description`, antikeywords, location, banned seller):

- **Logs:** Those lines are normal **INFO** logging only. There is no separate “skipped listings” database for faster matching; use your log files or terminal history if you want to review them.
- **PostgreSQL:** Skipped listings are **not** passed into the monitor’s main loop, so they are **not** upserted via `observe_listing` from that path (unlike listings that pass filters and get AI evaluation / tracking).
- **Disk cache:** After a listing **detail page** is opened and parsed successfully, details are stored in **diskcache** under `~/.ai-marketplace-monitor/` (`Listing.to_cache`). That cache **survives closing the browser** and **new Playwright sessions**. If the same item URL appears again with the **same SERP title and price**, the scanner can **reuse cached details** and skip navigating to the listing tab again.
- **What still happens every run:** Marketplace **search** still runs in the browser; result cards are still walked. Caching only avoids **repeat detail-page fetches** when the cache entry matches, not “hide this URL from search forever.”
- **Shallow stable skip** (`AIMM_SHALLOW_STABLE_SKIP`): separate feature; it uses PostgreSQL (same price + prior AI row). Keyword-only skips do **not** enable that path by themselves.

## Terminal output when something matches

You do not need Discord or any other notifier to see hits in the terminal. After each search, when at least one listing passes the AI score threshold, a **compact summary** is printed to **stderr**:

```text
[found] your-item-name: 2 listing(s)
  Title here | 500 kr | https://www.facebook.com/marketplace/item/...
  Other title | 300 kr | https://...
```

- One header line: `[found]`, the item name from config, and how many listings matched.
- One line per listing: title, price, and URL (query string stripped). If the listing was AI-evaluated, the line ends with  `| conclusion (score)` (short form, not the full AI comment).

This behavior is now first-class fork logic in `ai_marketplace_monitor/monitor.py` (no runtime patching required).

### Disable it

Set in `.env`:

```bash
AIMM_PRINT_FOUND=0
```

Accepted “off” values: `0`, `false`, `no`, `off` (case-insensitive).
---

## Dashboard (FastAPI + React)

A read-only local dashboard for browsing the PostgreSQL cache — listings with AI evaluations, price history, and notification events.

### Requirements

- Python 3.11+ (for the API)
- Node 18+ (for the frontend)
- PostgreSQL cache populated by at least one monitor run (`AIMM_PG_CACHE_ENABLED=1`)

### Start the API

```bash
cd backend
./start.sh          # creates .venv, installs deps, starts uvicorn on http://127.0.0.1:8000
```

Or manually:
```bash
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
# ensure AIMM_DATABASE_URL or DATABASE_URL is set (inherited from repo .env by start.sh)
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Start the frontend

```bash
cd frontend
npm install         # first time only
npm run dev         # Vite dev server at http://127.0.0.1:5173
```

Open http://127.0.0.1:5173 in your browser.

### Alembic (baseline stamp)

The schema is owned by `pg_cache.ensure_database()`. After first install, stamp Alembic so future dashboard-specific migrations work cleanly:

```bash
cd backend
.venv/bin/alembic stamp head
```

### API endpoints

| Endpoint | Description |
|---|---|
| `GET /api/listings` | Listings + latest AI evaluation. Filter: title, score_min/max, listing_kind, marketplace, date ranges. Sort: last_seen_at, score, title, evaluated_at. |
| `GET /api/listing-price-history` | Price change log. Filter: listing_id, date range. |
| `GET /api/notification-events` | Notification log. Filter: channel, status, listing_id, date range. |

All endpoints support `page`, `page_size`, `sort_dir`. Full OpenAPI docs: http://127.0.0.1:8000/docs
