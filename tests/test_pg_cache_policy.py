from __future__ import annotations

import sys
import types
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import MagicMock


class _FakeCache:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass


sys.modules.setdefault("diskcache", types.SimpleNamespace(Cache=_FakeCache))
sys.modules.setdefault("parsedatetime", types.SimpleNamespace())
sys.modules.setdefault("playwright", types.SimpleNamespace())
sys.modules.setdefault("playwright.sync_api", types.SimpleNamespace(ProxySettings=object))
sys.modules.setdefault("watchdog", types.SimpleNamespace())
sys.modules.setdefault(
    "watchdog.events",
    types.SimpleNamespace(FileSystemEvent=object, FileSystemEventHandler=object),
)
sys.modules.setdefault("watchdog.observers", types.SimpleNamespace(Observer=object))

from ai_marketplace_monitor.listing import Listing
from ai_marketplace_monitor.pg_cache import _upsert_listing, should_reuse_evaluation


class PgCachePolicyTests(TestCase):
    def test_reuse_when_unchanged(self) -> None:
        reuse, reason = should_reuse_evaluation(
            previous_price="5000",
            previous_content_hash="abc",
            evaluated_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            current_price="5000",
            current_content_hash="abc",
            cooldown_mins=0,
            reeval_price=True,
            reeval_content=True,
        )
        self.assertTrue(reuse)
        self.assertEqual(reason, "unchanged")

    def test_miss_on_price_change_without_cooldown(self) -> None:
        reuse, reason = should_reuse_evaluation(
            previous_price="5000",
            previous_content_hash="abc",
            evaluated_at=datetime.now(timezone.utc) - timedelta(minutes=30),
            current_price="4900",
            current_content_hash="abc",
            cooldown_mins=0,
            reeval_price=True,
            reeval_content=True,
        )
        self.assertFalse(reuse)
        self.assertEqual(reason, "price_changed")

    def test_reuse_during_cooldown_even_if_changed(self) -> None:
        reuse, reason = should_reuse_evaluation(
            previous_price="5000",
            previous_content_hash="abc",
            evaluated_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            current_price="4900",
            current_content_hash="xyz",
            cooldown_mins=10,
            reeval_price=True,
            reeval_content=True,
        )
        self.assertTrue(reuse)
        self.assertEqual(reason, "cooldown_active")

    def test_removed_listing_update_preserves_existing_metadata(self) -> None:
        cur = MagicMock()
        cur.fetchone.side_effect = [
            (12, "4500", "Till Salu"),
            (12,),
        ]
        listing = Listing(
            marketplace="facebook",
            name="",
            id="12345",
            title="Borttagen",
            image="",
            price="",
            post_url="https://www.facebook.com/marketplace/item/12345",
            location="",
            seller="",
            condition="",
            description="Det här inlägget finns inte längre",
            availability="Borttagen",
            original_price="",
        )

        internal_id = _upsert_listing(cur, listing)

        self.assertEqual(internal_id, 12)
        upsert_sql = cur.execute.call_args_list[1].args[0]
        upsert_params = cur.execute.call_args_list[1].args[1]
        self.assertIn("WHEN EXCLUDED.availability = %s THEN listings.title", upsert_sql)
        self.assertIn("WHEN EXCLUDED.availability = %s THEN listings.current_price", upsert_sql)
        self.assertEqual(upsert_params[-8:], ("Borttagen",) * 8)
