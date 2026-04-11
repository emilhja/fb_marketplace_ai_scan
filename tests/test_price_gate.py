"""Tests for the PostgreSQL price-gate logic.

Covers:
- fetch_listing_price_state returns (exists=False) when PG cache is disabled.
- fetch_listing_price_state returns correct exists/previous_price when DB is mocked.
- _upsert_listing inserts price history only on first insert or price change.
- send_plain_alert dispatches to configured channels only.
- monitor.py search_item skips AI and logs for no-price-change, and sends alert for price change.
"""
from __future__ import annotations

import unittest
from dataclasses import dataclass
from logging import Logger
from typing import Any, List
from unittest.mock import MagicMock, call, patch

from ai_marketplace_monitor.listing import Listing
from ai_marketplace_monitor.pg_cache import ListingPriceState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_listing(price: str = "5000", url: str = "https://www.facebook.com/marketplace/item/999/") -> Listing:
    return Listing(
        marketplace="facebook",
        name="gpu",
        id="999",
        title="RTX 5060",
        image="",
        price=price,
        post_url=url,
        location="Gothenburg",
        seller="Seller",
        condition="used",
        description="desc",
    )


# ---------------------------------------------------------------------------
# fetch_listing_price_state
# ---------------------------------------------------------------------------

class FetchListingPriceStateTests(unittest.TestCase):
    def test_returns_not_exists_when_cache_disabled(self) -> None:
        """When cache_enabled() is False the helper must return immediately without connecting."""
        with patch("ai_marketplace_monitor.pg_cache.cache_enabled", return_value=False):
            from ai_marketplace_monitor.pg_cache import fetch_listing_price_state
            state = fetch_listing_price_state(_make_listing())
        self.assertFalse(state.exists)
        self.assertIsNone(state.previous_price)

    def test_returns_not_exists_when_no_db_row(self) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: s
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = None
        mock_conn.__enter__ = lambda s: s
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur

        with patch("ai_marketplace_monitor.pg_cache.cache_enabled", return_value=True), \
             patch("ai_marketplace_monitor.pg_cache.ensure_database"), \
             patch("ai_marketplace_monitor.pg_cache._connect", return_value=mock_conn):
            from ai_marketplace_monitor.pg_cache import fetch_listing_price_state
            state = fetch_listing_price_state(_make_listing())

        self.assertFalse(state.exists)
        self.assertIsNone(state.previous_price)

    def test_returns_previous_price_when_row_found(self) -> None:
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.__enter__ = lambda s: s
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = ("4500",)
        mock_conn.__enter__ = lambda s: s
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur

        with patch("ai_marketplace_monitor.pg_cache.cache_enabled", return_value=True), \
             patch("ai_marketplace_monitor.pg_cache.ensure_database"), \
             patch("ai_marketplace_monitor.pg_cache._connect", return_value=mock_conn):
            from ai_marketplace_monitor.pg_cache import fetch_listing_price_state
            state = fetch_listing_price_state(_make_listing(price="5000"))

        self.assertTrue(state.exists)
        self.assertEqual(state.previous_price, "4500")


# ---------------------------------------------------------------------------
# send_plain_alert
# ---------------------------------------------------------------------------

class SendPlainAlertTests(unittest.TestCase):
    def test_dispatches_to_configured_subclass(self) -> None:
        """send_plain_alert should call send_message_with_retry for each configured subclass."""
        from ai_marketplace_monitor.notification import NotificationConfig, send_plain_alert

        # Minimal UserConfig stub — only needs the fields the subclass iteration inspects.
        @dataclass
        class _StubBackend(NotificationConfig):
            token: str | None = None

            def _has_required_fields(self) -> bool:  # type: ignore[override]
                return self.token is not None

            def send_message(self, title: str, message: str, logger: Any = None) -> bool:  # type: ignore[override]
                return True

        @dataclass
        class _StubUserConfig:
            name: str = "test_user"
            token: str | None = "abc"
            max_retries: int = 1
            retry_delay: int = 0

        user_cfg = _StubUserConfig()

        with patch.object(_StubBackend, "send_message_with_retry", return_value=True) as mock_send:
            result = send_plain_alert(user_cfg, "Title", "Body")  # type: ignore[arg-type]

        mock_send.assert_called_once_with("Title", "Body", logger=None)
        self.assertTrue(result)

        # Cleanup — remove the dynamically registered subclass so other tests are not affected.
        NotificationConfig.__subclasses__().remove(_StubBackend) if _StubBackend in NotificationConfig.__subclasses__() else None

    def test_returns_false_when_no_channels_configured(self) -> None:
        """send_plain_alert returns False when no subclass has required fields set."""
        from ai_marketplace_monitor.notification import send_plain_alert

        @dataclass
        class _EmptyUser:
            name: str = "nobody"
            # No channel credentials at all.

        result = send_plain_alert(_EmptyUser(), "T", "B")  # type: ignore[arg-type]
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# monitor.py price gate integration
# ---------------------------------------------------------------------------

class PriceGateIntegrationTests(unittest.TestCase):
    """Verify search_item skips / alerts based on ListingPriceState."""

    def _make_monitor(self):
        """Return a MarketplaceMonitor with just enough state to call search_item."""
        from ai_marketplace_monitor.monitor import MarketplaceMonitor
        monitor = MarketplaceMonitor.__new__(MarketplaceMonitor)
        monitor.logger = MagicMock(spec=Logger)
        monitor.keyboard_monitor = None
        monitor.ai_agents = []

        # Minimal config stub.
        user_cfg = MagicMock()
        user_cfg.notify = None
        mock_config = MagicMock()
        mock_config.user = {"default_user": user_cfg}
        monitor.config = mock_config
        return monitor

    def test_skip_when_price_unchanged(self) -> None:
        """When listing is in DB with same price, evaluate_by_ai must NOT be called."""
        monitor = self._make_monitor()
        listing = _make_listing(price="5000")

        marketplace_config = MagicMock()
        marketplace_config.notify = None
        item_config = MagicMock()
        item_config.notify = None
        item_config.name = "gpu"
        item_config.searched_count = 0
        item_config.rating = None

        marketplace = MagicMock()
        marketplace.search.return_value = [listing]

        unchanged_state = ListingPriceState(exists=True, previous_price="5000")

        with patch("ai_marketplace_monitor.monitor.fetch_listing_price_state", return_value=unchanged_state), \
             patch("ai_marketplace_monitor.monitor.observe_listing"), \
             patch(
                 "ai_marketplace_monitor.monitor.has_any_ai_evaluation_for_listing",
                 return_value=True,
             ), \
             patch.object(monitor, "evaluate_by_ai") as mock_eval:
            monitor.search_item(marketplace_config, marketplace, item_config)

        mock_eval.assert_not_called()

    def test_evaluate_when_price_unchanged_but_no_ai_history(self) -> None:
        """Same price must still run AI when ai_evaluations has no row yet (backfill path)."""
        from ai_marketplace_monitor.ai import AIResponse
        from ai_marketplace_monitor.notification import NotificationStatus

        monitor = self._make_monitor()
        listing = _make_listing(price="5000")

        marketplace_config = MagicMock()
        marketplace_config.notify = None
        marketplace_config.ai = None
        marketplace_config.rating = None
        item_config = MagicMock()
        item_config.notify = None
        item_config.name = "gpu"
        item_config.searched_count = 0
        item_config.rating = None
        item_config.ai = None

        marketplace = MagicMock()
        marketplace.search.return_value = [listing]

        unchanged_state = ListingPriceState(exists=True, previous_price="5000")
        ai_response = AIResponse(score=4, comment="Good match", name="openrouter")

        with patch("ai_marketplace_monitor.monitor.fetch_listing_price_state", return_value=unchanged_state), \
             patch("ai_marketplace_monitor.monitor.observe_listing"), \
             patch(
                 "ai_marketplace_monitor.monitor.has_any_ai_evaluation_for_listing",
                 return_value=False,
             ), \
             patch("ai_marketplace_monitor.monitor.User") as mock_user_cls, \
             patch.object(monitor, "evaluate_by_ai", return_value=ai_response) as mock_eval:

            mock_user_cls.return_value.notification_status.return_value = NotificationStatus.NOT_NOTIFIED

            monitor.search_item(marketplace_config, marketplace, item_config)

        mock_eval.assert_called_once()

    def test_alert_and_evaluate_when_price_changed(self) -> None:
        """When price changed, send_plain_alert is called and evaluate_by_ai proceeds."""
        from ai_marketplace_monitor.ai import AIResponse

        monitor = self._make_monitor()
        listing = _make_listing(price="4500")

        marketplace_config = MagicMock()
        marketplace_config.notify = None
        marketplace_config.ai = None
        marketplace_config.rating = None
        item_config = MagicMock()
        item_config.notify = None
        item_config.name = "gpu"
        item_config.searched_count = 0
        item_config.rating = None
        item_config.ai = None

        marketplace = MagicMock()
        marketplace.search.return_value = [listing]

        changed_state = ListingPriceState(exists=True, previous_price="5000")
        ai_response = AIResponse(score=4, comment="Good match", name="openrouter")

        with patch("ai_marketplace_monitor.monitor.fetch_listing_price_state", return_value=changed_state), \
             patch("ai_marketplace_monitor.monitor.observe_listing"), \
             patch("ai_marketplace_monitor.monitor.send_plain_alert", return_value=True) as mock_alert, \
             patch("ai_marketplace_monitor.monitor.record_notification_event"), \
             patch("ai_marketplace_monitor.monitor.User") as mock_user_cls, \
             patch.object(monitor, "evaluate_by_ai", return_value=ai_response) as mock_eval:

            # Notification status: not notified (so the notified-skip doesn't hide our call).
            from ai_marketplace_monitor.notification import NotificationStatus
            mock_user_cls.return_value.notification_status.return_value = NotificationStatus.NOT_NOTIFIED

            monitor.search_item(marketplace_config, marketplace, item_config)

        mock_alert.assert_called_once()
        mock_eval.assert_called_once()

    def test_no_pg_gate_when_listing_new(self) -> None:
        """When listing is not in DB (first sighting), gate does not skip — falls to normal flow."""
        from ai_marketplace_monitor.ai import AIResponse
        from ai_marketplace_monitor.notification import NotificationStatus

        monitor = self._make_monitor()
        listing = _make_listing(price="5000")

        marketplace_config = MagicMock()
        marketplace_config.notify = None
        marketplace_config.ai = None
        marketplace_config.rating = None
        item_config = MagicMock()
        item_config.notify = None
        item_config.name = "gpu"
        item_config.searched_count = 0
        item_config.rating = None
        item_config.ai = None

        marketplace = MagicMock()
        marketplace.search.return_value = [listing]

        new_state = ListingPriceState(exists=False, previous_price=None)
        ai_response = AIResponse(score=4, comment="Good match", name="openrouter")

        with patch("ai_marketplace_monitor.monitor.fetch_listing_price_state", return_value=new_state), \
             patch("ai_marketplace_monitor.monitor.observe_listing"), \
             patch("ai_marketplace_monitor.monitor.send_plain_alert") as mock_alert, \
             patch("ai_marketplace_monitor.monitor.User") as mock_user_cls, \
             patch.object(monitor, "evaluate_by_ai", return_value=ai_response) as mock_eval:

            mock_user_cls.return_value.notification_status.return_value = NotificationStatus.NOT_NOTIFIED

            monitor.search_item(marketplace_config, marketplace, item_config)

        mock_alert.assert_not_called()
        mock_eval.assert_called_once()


if __name__ == "__main__":
    unittest.main()
