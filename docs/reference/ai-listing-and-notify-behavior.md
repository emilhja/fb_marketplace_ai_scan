# AI calls, listing cache, and “already notified” behavior

This project runs a local hard fork of **ai-marketplace-monitor** (see `run.sh`). Core logic now lives in this repo under `ai_marketplace_monitor/`.

## Can the same article be sent to the AI several times?

**Yes.** There is **no** persistent flag meaning “we already called the model for this listing URL.” Whether the AI runs again is **not** tied to a prior successful parse.

The monitor **only** skips the AI step when **every** user who should be notified for that search item is still in state `**NOTIFIED`** for that listing (see below). In all other cases, `**evaluate_by_ai` can run again** on the same listing on later scans.

## When the AI is **not** called again for the same listing

Before calling the AI, `monitor.py` checks notification status for each listing:

- It builds `**users_to_notify`** from the item config, else marketplace config, else all users in `config.toml`.
- If **for every** user in that list, `notification_status(listing) == NOTIFIED`, the listing is **skipped** (log line like “Already sent notification…”) and `**evaluate_by_ai` is not invoked**.

So “skip” means: **everyone who should get alerts for this item has already been notified for this listing**, and the app still considers that notification **current** (unchanged listing, within `remind` if configured, etc.—see `user.py`).

## When the same listing **is** sent to the AI again (common cases)


| Situation                                                    | Typical outcome                                                                                         |
| ------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| AI score **below** your configured threshold                 | No notification is stored as for a fresh hit → next scan → **AI runs again**.                           |
| User’s `**remind`** window **expired**                       | Status is `**EXPIRED`**, not `**NOTIFIED**` → **no** “everyone notified” skip → **AI can run again**.   |
| Listing **hash** changed or **price drop** detected vs cache | Status `**LISTING_CHANGED`** or `**LISTING_DISCOUNTED**` → skip condition fails → **AI can run again**. |
| Not **all** users in `users_to_notify` are `**NOTIFIED`**    | Skip requires **all** → **AI runs again**.                                                              |


## Opening the listing page in the browser (separate from AI)

**Listing detail cache** (`Listing.from_cache` / `to_cache` in `listing.py`, used from `facebook.py` → `get_listing_details`) can avoid **navigating** to the item URL again if details are cached **and** the search snippet’s **title and price** still match. That reduces repeated **page opens**; it does **not** replace “don’t call the AI again.”

## Summary

- **Duplicate AI calls on the same article are possible** whenever the “already notified **everyone**” condition is false.
- **Skipping AI** is driven by **notification cache + status**, not by “AI already evaluated this URL.”

## Local fork PostgreSQL dedupe mode

When `AIMM_DATABASE_URL` is configured and `AIMM_PG_CACHE_ENABLED=1`, the local patch layer adds an extra AI cache in PostgreSQL:

- AI is reused when listing content + price are unchanged for the same model and prompt hash/version.
- AI is re-run on price/content change when enabled (`AIMM_REEVAL_ON_PRICE_CHANGE`, `AIMM_REEVAL_ON_CONTENT_CHANGE`).
- A cooldown (`AIMM_AI_REEVAL_COOLDOWN_MINUTES`) can temporarily reuse previous results even after changes.

This is fork behavior in `ai_marketplace_monitor/pg_cache.py` + `ai_marketplace_monitor/ai.py` + `ai_marketplace_monitor/monitor.py`, not upstream default behavior.
