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