# Hashing logic in the `ai_evaluations` table

PostgreSQL rows in `ai_evaluations` store a model’s score and text for a specific listing **under a specific evaluation context**. Hashes and related keys exist so the monitor can **reuse** past completions safely (fewer API calls, stable history) without treating an old answer as valid when the **question** or the **listing facts** have changed.

Implementation lives in `ai_marketplace_monitor/pg_cache.py`.

## Fields and why they exist

### `item_config_hash` / `marketplace_config_hash`

These identify **which item block** (search criteria, phrases, keywords, etc.) and **which marketplace block** in config produced the evaluation.

If you change criteria, duplicate an item, or use another marketplace profile, you must not reuse a score that was produced for a different search. The cache lookup matches on both hashes together with `listing_id`, `model`, `prompt_version`, and `prompt_hash`:

```451:462:ai_marketplace_monitor/pg_cache.py
                    SELECT score, conclusion, comment, listing_price, content_hash, evaluated_at,
                           response_model, COALESCE(listing_kind, 'unknown') AS listing_kind
                    FROM ai_evaluations
                    WHERE listing_id = %s
                      AND model = %s
                      AND item_config_hash = %s
                      AND marketplace_config_hash = %s
                      AND prompt_version = %s
                      AND prompt_hash = %s
                    ORDER BY evaluated_at DESC
                    LIMIT 1;
```

### `prompt_hash`

SHA-256 of the **full prompt string** sent to the model (`prompt_hash(prompt)` in code). Any change to baked-in listing text, `description` / `extra_prompt` / rating instructions, or other prompt content produces a new hash, i.e. a **new evaluation contract**. That prevents reusing a score that answered a **different** question.

### `prompt_version`

String from the environment variable **`AIMM_PROMPT_VERSION`** (default `v1`). Lets you **invalidate all cached evaluations** without editing prompt text—for example after changing scoring semantics or DB columns that affect how you interpret stored rows.

### `content_hash` (stored on each evaluation row)

Fingerprint of the listing snapshot at evaluation time (`listing_content_hash`: title, description, seller, condition, URLs, etc.). Compared to the **current** listing’s content hash when deciding whether a cached row is still valid.

### `listing_price` (stored on each evaluation row)

The listing’s price string at evaluation time. Used with `content_hash` in **`should_reuse_evaluation`** so the cache can miss when price or content changed (subject to `AIMM_REEVAL_ON_PRICE_CHANGE`, `AIMM_REEVAL_ON_CONTENT_CHANGE`, and optional cooldown).

## How reuse is decided

After loading the latest matching row, the code compares stored `listing_price` and `content_hash` to the current listing and applies re-eval and cooldown rules:

```124:147:ai_marketplace_monitor/pg_cache.py
def should_reuse_evaluation(
    *,
    previous_price: str,
    previous_content_hash: str,
    evaluated_at: datetime,
    current_price: str,
    current_content_hash: str,
    cooldown_mins: int,
    reeval_price: bool,
    reeval_content: bool,
) -> tuple[bool, str]:
    price_changed = previous_price != current_price
    content_changed = previous_content_hash != current_content_hash
    cooldown_active = False
    if cooldown_mins > 0:
        cooldown_active = evaluated_at + timedelta(minutes=cooldown_mins) > _utc_now()

    if price_changed and reeval_price and not cooldown_active:
        return False, "price_changed"
    if content_changed and reeval_content and not cooldown_active:
        return False, "content_changed"
    if cooldown_active and (price_changed or content_changed):
        return True, "cooldown_active"
    return True, "unchanged"
```

## One-sentence summary

**Config and prompt hashes version the “question”; stored price and content hash version the “facts,” so PostgreSQL can reuse AI results only when it is still appropriate.**
