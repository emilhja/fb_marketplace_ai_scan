from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .listing import Listing

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore[assignment]


LISTING_ID_RE = re.compile(r"/item/(\d+)")


@dataclass
class CachedAIResult:
    score: int
    conclusion: str
    comment: str
    model: str
    reason: str
    # Actual completion model from the API (e.g. OpenRouter-routed id); may be NULL in old DB rows.
    response_model: str | None = None


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _db_url() -> str | None:
    return os.environ.get("AIMM_DATABASE_URL") or os.environ.get("DATABASE_URL")


def cache_enabled() -> bool:
    if not _truthy(os.environ.get("AIMM_PG_CACHE_ENABLED"), default=True):
        return False
    return bool(_db_url()) and psycopg is not None


def _connect():
    url = _db_url()
    if not url:
        raise RuntimeError("AIMM_DATABASE_URL or DATABASE_URL is required")
    if psycopg is None:
        raise RuntimeError("psycopg is not installed")
    return psycopg.connect(url)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_url(url: str) -> str:
    return (url or "").split("?")[0].strip()


def extract_marketplace_listing_id(post_url: str, fallback_id: str | None = None) -> str:
    m = LISTING_ID_RE.search(normalize_url(post_url))
    if m:
        return m.group(1)
    if fallback_id:
        return str(fallback_id)
    digest = hashlib.sha256(normalize_url(post_url).encode("utf-8")).hexdigest()[:24]
    return f"url:{digest}"


def listing_key_from_listing(listing: Listing) -> str:
    listing_id = extract_marketplace_listing_id(listing.post_url, listing.id)
    return f"{listing.marketplace}:{listing_id}"


def listing_content_hash(listing: Listing) -> str:
    payload = {
        "marketplace": listing.marketplace,
        "listing_id": extract_marketplace_listing_id(listing.post_url, listing.id),
        "name": listing.name,
        "title": listing.title,
        "location": listing.location,
        "seller": listing.seller,
        "condition": listing.condition,
        "description": listing.description,
        "post_url": normalize_url(listing.post_url),
        "original_price": listing.original_price or "",
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256((prompt or "").encode("utf-8")).hexdigest()


def prompt_version() -> str:
    raw = (os.environ.get("AIMM_PROMPT_VERSION") or "v1").strip()
    return raw or "v1"


def cooldown_minutes() -> int:
    raw = (os.environ.get("AIMM_AI_REEVAL_COOLDOWN_MINUTES") or "0").strip()
    try:
        parsed = int(raw)
    except ValueError:
        parsed = 0
    return max(0, parsed)


def reeval_on_price_change() -> bool:
    return _truthy(os.environ.get("AIMM_REEVAL_ON_PRICE_CHANGE"), default=True)


def reeval_on_content_change() -> bool:
    return _truthy(os.environ.get("AIMM_REEVAL_ON_CONTENT_CHANGE"), default=True)


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


def ensure_database() -> bool:
    if not cache_enabled():
        return False

    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS listings (
                    id BIGSERIAL PRIMARY KEY,
                    listing_key TEXT UNIQUE NOT NULL,
                    marketplace TEXT NOT NULL,
                    marketplace_listing_id TEXT NOT NULL,
                    canonical_post_url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    current_price TEXT NOT NULL,
                    last_content_hash TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    location TEXT NOT NULL DEFAULT '',
                    skick TEXT NOT NULL DEFAULT '',
                    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                ALTER TABLE listings
                ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT '';
                """
            )
            cur.execute(
                """
                ALTER TABLE listings
                ADD COLUMN IF NOT EXISTS location TEXT NOT NULL DEFAULT '';
                """
            )
            cur.execute(
                """
                ALTER TABLE listings
                ADD COLUMN IF NOT EXISTS skick TEXT NOT NULL DEFAULT '';
                """
            )
            cur.execute(
                """
                ALTER TABLE listings
                ADD COLUMN IF NOT EXISTS original_price TEXT NOT NULL DEFAULT '';
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS listing_price_history (
                    id BIGSERIAL PRIMARY KEY,
                    listing_id BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
                    price TEXT NOT NULL,
                    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_listing_price_history_listing_time
                ON listing_price_history (listing_id, observed_at DESC);
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_evaluations (
                    id BIGSERIAL PRIMARY KEY,
                    listing_id BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
                    model TEXT NOT NULL,
                    item_config_hash TEXT NOT NULL,
                    marketplace_config_hash TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    prompt_hash TEXT NOT NULL,
                    listing_price TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    conclusion TEXT NOT NULL,
                    comment TEXT NOT NULL,
                    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ai_evaluations_lookup
                ON ai_evaluations (
                    listing_id, model, item_config_hash, marketplace_config_hash, prompt_version, prompt_hash, evaluated_at DESC
                );
                """
            )
            cur.execute(
                """
                ALTER TABLE ai_evaluations
                ADD COLUMN IF NOT EXISTS response_model TEXT;
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS notification_events (
                    id BIGSERIAL PRIMARY KEY,
                    listing_id BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
                    user_name TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    status TEXT NOT NULL,
                    details JSONB,
                    sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_notification_events_listing_time
                ON notification_events (listing_id, sent_at DESC);
                """
            )
        conn.commit()
    return True


@dataclass
class ListingPriceState:
    """Result of fetch_listing_price_state."""
    exists: bool
    previous_price: str | None  # None when listing not yet in DB


def has_any_ai_evaluation_for_listing(listing: Listing, logger: Any = None) -> bool:
    """True if PostgreSQL has at least one ai_evaluations row for this marketplace listing."""
    if not cache_enabled():
        return False
    key = listing_key_from_listing(listing)
    try:
        ensure_database()
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM ai_evaluations e
                        INNER JOIN listings l ON l.id = e.listing_id
                        WHERE l.listing_key = %s
                    );
                    """,
                    (key,),
                )
                row = cur.fetchone()
        return bool(row and row[0])
    except Exception as exc:  # pragma: no cover
        if logger:
            logger.debug(f"[AIMM-DB] has_any_ai_evaluation_for_listing failed: {exc}")
        return False


def should_skip_stable_detail_fetch(listing: Listing, logger: Any = None) -> bool:
    """True when the listing is stable enough to skip Playwright detail navigation.

    Mirrors the monitor.py AI-skip gate: we skip only when PostgreSQL confirms
    (a) the listing exists, (b) price has not changed since the last observed value,
    and (c) at least one AI evaluation has already been persisted.  All three
    conditions must hold; otherwise we fall through to a full detail fetch as usual.

    Note: SERP price may occasionally differ from the stored detail-page price due to
    scraping differences.  When that happens this function returns False (safe default:
    force a fresh fetch).
    """
    if not cache_enabled():
        return False
    price_state = fetch_listing_price_state(listing, logger=logger)
    if not price_state.exists:
        return False
    if price_state.previous_price != listing.price:
        return False
    return has_any_ai_evaluation_for_listing(listing, logger=logger)


def fetch_listing_price_state(listing: Listing, logger: Any = None) -> ListingPriceState:
    """Return whether the listing exists in DB and what its stored price is, without writing."""
    if not cache_enabled():
        return ListingPriceState(exists=False, previous_price=None)
    key = listing_key_from_listing(listing)
    try:
        ensure_database()
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT current_price FROM listings WHERE listing_key = %s LIMIT 1;",
                    (key,),
                )
                row = cur.fetchone()
        if row is None:
            return ListingPriceState(exists=False, previous_price=None)
        return ListingPriceState(exists=True, previous_price=str(row[0]))
    except Exception as exc:  # pragma: no cover
        if logger:
            logger.debug(f"[AIMM-DB] fetch_listing_price_state failed: {exc}")
        return ListingPriceState(exists=False, previous_price=None)


def _upsert_listing(cur: Any, listing: Listing) -> int:
    """Upsert listing row and insert price history only when price is new or changed."""
    listing_id = extract_marketplace_listing_id(listing.post_url, listing.id)
    key = f"{listing.marketplace}:{listing_id}"

    # Read the stored price before upserting so we can decide whether to add a history row.
    cur.execute("SELECT id, current_price FROM listings WHERE listing_key = %s LIMIT 1;", (key,))
    existing = cur.fetchone()
    previous_price: str | None = str(existing[1]) if existing is not None else None

    cur.execute(
        """
        INSERT INTO listings (
            listing_key, marketplace, marketplace_listing_id, canonical_post_url,
            title, current_price, original_price, last_content_hash,
            description, location, skick
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (listing_key)
        DO UPDATE SET
            title = EXCLUDED.title,
            current_price = EXCLUDED.current_price,
            original_price = EXCLUDED.original_price,
            last_content_hash = EXCLUDED.last_content_hash,
            description = EXCLUDED.description,
            location = EXCLUDED.location,
            skick = EXCLUDED.skick,
            last_seen_at = NOW(),
            updated_at = NOW()
        RETURNING id;
        """,
        (
            key,
            listing.marketplace,
            listing_id,
            normalize_url(listing.post_url),
            listing.title,
            listing.price,
            listing.original_price or "",
            listing_content_hash(listing),
            listing.description or "",
            listing.location or "",
            listing.condition or "",
        ),
    )
    internal_id = int(cur.fetchone()[0])

    # Only record a price history entry when price actually changes (or on first insert).
    if previous_price is None or previous_price != listing.price:
        cur.execute(
            """
            INSERT INTO listing_price_history (listing_id, price, observed_at)
            VALUES (%s, %s, NOW());
            """,
            (internal_id, listing.price),
        )
    return internal_id


def observe_listing(listing: Listing, logger: Any = None) -> Optional[str]:
    if not cache_enabled():
        return None
    try:
        ensure_database()
        with _connect() as conn:
            with conn.cursor() as cur:
                _upsert_listing(cur, listing)
            conn.commit()
        return listing_key_from_listing(listing)
    except Exception as exc:  # pragma: no cover
        if logger:
            logger.debug(f"[AIMM-DB] observe_listing failed: {exc}")
        return None


def get_cached_ai_response(
    *,
    listing: Listing,
    model: str,
    prompt: str,
    item_config_hash: str,
    marketplace_config_hash: str,
    logger: Any = None,
) -> Optional[CachedAIResult]:
    if not cache_enabled():
        return None
    try:
        ensure_database()
        with _connect() as conn:
            with conn.cursor() as cur:
                listing_id = _upsert_listing(cur, listing)
                cur.execute(
                    """
                    SELECT score, conclusion, comment, listing_price, content_hash, evaluated_at,
                           response_model
                    FROM ai_evaluations
                    WHERE listing_id = %s
                      AND model = %s
                      AND item_config_hash = %s
                      AND marketplace_config_hash = %s
                      AND prompt_version = %s
                      AND prompt_hash = %s
                    ORDER BY evaluated_at DESC
                    LIMIT 1;
                    """,
                    (
                        listing_id,
                        model,
                        item_config_hash,
                        marketplace_config_hash,
                        prompt_version(),
                        prompt_hash(prompt),
                    ),
                )
                row = cur.fetchone()
            conn.commit()
        if row is None:
            if logger:
                logger.info("[AIMM-DB] ai_cache_miss reason=no_previous_eval")
            return None

        score, conclusion, comment, prev_price, prev_hash, evaluated_at, resp_model = row
        can_reuse, reason = should_reuse_evaluation(
            previous_price=str(prev_price or ""),
            previous_content_hash=str(prev_hash or ""),
            evaluated_at=evaluated_at,
            current_price=listing.price,
            current_content_hash=listing_content_hash(listing),
            cooldown_mins=cooldown_minutes(),
            reeval_price=reeval_on_price_change(),
            reeval_content=reeval_on_content_change(),
        )
        if not can_reuse:
            if logger:
                logger.info(f"[AIMM-DB] ai_cache_miss reason={reason}")
            return None

        if logger:
            logger.info(f"[AIMM-DB] ai_cache_hit reason={reason}")
        rm = resp_model if isinstance(resp_model, str) and resp_model.strip() else None
        return CachedAIResult(
            score=int(score),
            conclusion=str(conclusion or ""),
            comment=str(comment or ""),
            model=model,
            reason=reason,
            response_model=rm,
        )
    except Exception as exc:  # pragma: no cover
        if logger:
            logger.debug(f"[AIMM-DB] get_cached_ai_response failed: {exc}")
        return None


def store_ai_evaluation(
    *,
    listing: Listing,
    model: str,
    prompt: str,
    item_config_hash: str,
    marketplace_config_hash: str,
    score: int,
    conclusion: str,
    comment: str,
    response_model: str | None = None,
    logger: Any = None,
) -> None:
    if not cache_enabled():
        return
    try:
        ensure_database()
        with _connect() as conn:
            with conn.cursor() as cur:
                listing_id = _upsert_listing(cur, listing)
                cur.execute(
                    """
                    INSERT INTO ai_evaluations (
                        listing_id, model, item_config_hash, marketplace_config_hash, prompt_version, prompt_hash,
                        listing_price, content_hash, score, conclusion, comment, response_model, evaluated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW());
                    """,
                    (
                        listing_id,
                        model,
                        item_config_hash,
                        marketplace_config_hash,
                        prompt_version(),
                        prompt_hash(prompt),
                        listing.price,
                        listing_content_hash(listing),
                        score,
                        conclusion,
                        comment,
                        response_model,
                    ),
                )
            conn.commit()
        if logger:
            logger.info("[AIMM-DB] ai_eval_persisted")
    except Exception as exc:  # pragma: no cover
        if logger:
            logger.warning(f"[AIMM-DB] store_ai_evaluation failed: {exc}")


def store_ai_evaluation_if_absent(
    *,
    listing: Listing,
    model: str,
    prompt: str,
    item_config_hash: str,
    marketplace_config_hash: str,
    score: int,
    conclusion: str,
    comment: str,
    response_model: str | None = None,
    logger: Any = None,
) -> None:
    """Persist one AI row when missing (e.g. result served from disk cache after PG was enabled)."""
    if not cache_enabled():
        return
    try:
        ensure_database()
        pv = prompt_version()
        ph = prompt_hash(prompt)
        ch = listing_content_hash(listing)
        with _connect() as conn:
            with conn.cursor() as cur:
                listing_id = _upsert_listing(cur, listing)
                cur.execute(
                    """
                    SELECT 1 FROM ai_evaluations
                    WHERE listing_id = %s AND model = %s
                      AND item_config_hash = %s AND marketplace_config_hash = %s
                      AND prompt_version = %s AND prompt_hash = %s AND content_hash = %s
                    LIMIT 1;
                    """,
                    (
                        listing_id,
                        model,
                        item_config_hash,
                        marketplace_config_hash,
                        pv,
                        ph,
                        ch,
                    ),
                )
                if cur.fetchone() is not None:
                    conn.commit()
                    return
                cur.execute(
                    """
                    INSERT INTO ai_evaluations (
                        listing_id, model, item_config_hash, marketplace_config_hash, prompt_version, prompt_hash,
                        listing_price, content_hash, score, conclusion, comment, response_model, evaluated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW());
                    """,
                    (
                        listing_id,
                        model,
                        item_config_hash,
                        marketplace_config_hash,
                        pv,
                        ph,
                        listing.price,
                        ch,
                        score,
                        conclusion,
                        comment,
                        response_model,
                    ),
                )
            conn.commit()
        if logger:
            logger.info("[AIMM-DB] ai_eval_persisted (backfilled from disk cache)")
    except Exception as exc:  # pragma: no cover
        if logger:
            logger.warning(f"[AIMM-DB] store_ai_evaluation_if_absent failed: {exc}")


def record_notification_event(
    *,
    listing: Listing,
    user_name: str,
    channel: str,
    status: str,
    details: dict[str, Any] | None = None,
    logger: Any = None,
) -> None:
    if not cache_enabled():
        return
    try:
        ensure_database()
        with _connect() as conn:
            with conn.cursor() as cur:
                listing_id = _upsert_listing(cur, listing)
                cur.execute(
                    """
                    INSERT INTO notification_events (
                        listing_id, user_name, channel, status, details, sent_at
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb, NOW());
                    """,
                    (
                        listing_id,
                        user_name,
                        channel,
                        status,
                        json.dumps(details or {}, ensure_ascii=True),
                    ),
                )
            conn.commit()
    except Exception as exc:  # pragma: no cover
        if logger:
            logger.debug(f"[AIMM-DB] record_notification_event failed: {exc}")


def prune_old_records(retention_days: int, logger: Any = None) -> dict[str, int]:
    if not cache_enabled():
        return {"ai_evaluations": 0, "listing_price_history": 0, "notification_events": 0}
    retention_days = max(1, int(retention_days))
    deleted = {"ai_evaluations": 0, "listing_price_history": 0, "notification_events": 0}
    try:
        ensure_database()
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM ai_evaluations
                    WHERE evaluated_at < NOW() - (%s || ' days')::interval;
                    """,
                    (retention_days,),
                )
                deleted["ai_evaluations"] = int(cur.rowcount or 0)
                cur.execute(
                    """
                    DELETE FROM listing_price_history
                    WHERE observed_at < NOW() - (%s || ' days')::interval;
                    """,
                    (retention_days,),
                )
                deleted["listing_price_history"] = int(cur.rowcount or 0)
                cur.execute(
                    """
                    DELETE FROM notification_events
                    WHERE sent_at < NOW() - (%s || ' days')::interval;
                    """,
                    (retention_days,),
                )
                deleted["notification_events"] = int(cur.rowcount or 0)
            conn.commit()
        if logger:
            logger.info(f"[AIMM-DB] prune_complete retention_days={retention_days} deleted={deleted}")
    except Exception as exc:  # pragma: no cover
        if logger:
            logger.debug(f"[AIMM-DB] prune_old_records failed: {exc}")
    return deleted
