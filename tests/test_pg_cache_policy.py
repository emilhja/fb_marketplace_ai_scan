from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest import TestCase

from ai_marketplace_monitor.pg_cache import should_reuse_evaluation


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
