# Facebook Marketplace scan

Local wrapper around [ai-marketplace-monitor](https://pypi.org/project/ai-marketplace-monitor/): `./run.sh` loads `.env`, activates `.venv`, reapplies `scripts/apply_ai_marketplace_monitor_patches.py`, then runs `ai-marketplace-monitor`. Configure searches in `~/.ai-marketplace-monitor/config.toml` (see the upstream project for full options).

## Terminal output when something matches

You do not need Discord or any other notifier to see hits in the terminal. After each search, when at least one listing passes the AI score threshold, a **compact summary** is printed to **stderr**:

```text
[found] your-item-name: 2 listing(s)
  Title here | 500 kr | https://www.facebook.com/marketplace/item/...
  Other title | 300 kr | https://...
```

- One header line: `[found]`, the item name from config, and how many listings matched.
- One line per listing: title, price, and URL (query string stripped). If the listing was AI-evaluated, the line ends with ` | conclusion (score)` (short form, not the full AI comment).

This is applied by the `terminal_found` patch in `scripts/apply_ai_marketplace_monitor_patches.py` and is re-run every time you start via `./run.sh`, so it survives `pip` upgrades until upstream `monitor.py` changes enough that the patch needs updating.

### Disable it

Set in `.env`:

```bash
AIMM_PRINT_FOUND=0
```

Accepted “off” values: `0`, `false`, `no`, `off` (case-insensitive).
