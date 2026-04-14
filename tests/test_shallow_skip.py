"""Tests for the shallow stable-listing skip (AIMM_SHALLOW_STABLE_SKIP).

Covers:
- should_skip_stable_detail_fetch returns False when cache is disabled.
- should_skip_stable_detail_fetch returns False when listing is not in DB.
- should_skip_stable_detail_fetch returns False when price has changed.
- should_skip_stable_detail_fetch returns False when no AI evaluation exists.
- should_skip_stable_detail_fetch returns True only when all three conditions hold.
- FacebookMarketplace.search does NOT skip get_listing_details when flag is off.
- FacebookMarketplace.search skips get_listing_details for stable listings when flag is on.
- FacebookMarketplace.search does NOT skip get_listing_details for new/changed listings when flag is on.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch, call

from ai_marketplace_monitor.listing import Listing
from ai_marketplace_monitor.pg_cache import ListingPriceState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_listing(
    price: str = "5000",
    url: str = "https://www.facebook.com/marketplace/item/999/",
) -> Listing:
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
# should_skip_stable_detail_fetch unit tests
# ---------------------------------------------------------------------------


class ShouldSkipStableTests(unittest.TestCase):
    def test_returns_false_when_cache_disabled(self) -> None:
        with patch("ai_marketplace_monitor.pg_cache.cache_enabled", return_value=False):
            from ai_marketplace_monitor.pg_cache import should_skip_stable_detail_fetch

            result = should_skip_stable_detail_fetch(_make_listing())
        self.assertFalse(result)

    def test_returns_false_when_not_in_db(self) -> None:
        not_in_db = ListingPriceState(exists=False, previous_price=None)
        with (
            patch("ai_marketplace_monitor.pg_cache.cache_enabled", return_value=True),
            patch(
                "ai_marketplace_monitor.pg_cache.fetch_listing_price_state", return_value=not_in_db
            ),
        ):
            from ai_marketplace_monitor.pg_cache import should_skip_stable_detail_fetch

            result = should_skip_stable_detail_fetch(_make_listing())
        self.assertFalse(result)

    def test_returns_false_when_price_changed(self) -> None:
        changed = ListingPriceState(exists=True, previous_price="4000")
        with (
            patch("ai_marketplace_monitor.pg_cache.cache_enabled", return_value=True),
            patch(
                "ai_marketplace_monitor.pg_cache.fetch_listing_price_state", return_value=changed
            ),
        ):
            from ai_marketplace_monitor.pg_cache import should_skip_stable_detail_fetch

            result = should_skip_stable_detail_fetch(_make_listing(price="5000"))
        self.assertFalse(result)

    def test_returns_false_when_no_ai_evaluation(self) -> None:
        same_price = ListingPriceState(exists=True, previous_price="5000")
        with (
            patch("ai_marketplace_monitor.pg_cache.cache_enabled", return_value=True),
            patch(
                "ai_marketplace_monitor.pg_cache.fetch_listing_price_state", return_value=same_price
            ),
            patch(
                "ai_marketplace_monitor.pg_cache.has_any_ai_evaluation_for_listing",
                return_value=False,
            ),
        ):
            from ai_marketplace_monitor.pg_cache import should_skip_stable_detail_fetch

            result = should_skip_stable_detail_fetch(_make_listing())
        self.assertFalse(result)

    def test_returns_true_when_all_conditions_hold(self) -> None:
        same_price = ListingPriceState(exists=True, previous_price="5000")
        with (
            patch("ai_marketplace_monitor.pg_cache.cache_enabled", return_value=True),
            patch(
                "ai_marketplace_monitor.pg_cache.fetch_listing_price_state", return_value=same_price
            ),
            patch(
                "ai_marketplace_monitor.pg_cache.has_any_ai_evaluation_for_listing",
                return_value=True,
            ),
        ):
            from ai_marketplace_monitor.pg_cache import should_skip_stable_detail_fetch

            result = should_skip_stable_detail_fetch(_make_listing())
        self.assertTrue(result)


# ---------------------------------------------------------------------------
# FacebookMarketplace.search shallow-skip integration tests
# ---------------------------------------------------------------------------


def _make_fb_marketplace(page_stub: MagicMock | None = None) -> "FacebookMarketplace":
    from ai_marketplace_monitor.facebook import FacebookMarketplace

    fb = FacebookMarketplace.__new__(FacebookMarketplace)
    fb.logger = MagicMock()
    fb.keyboard_monitor = None
    fb.config = MagicMock()
    fb.config.condition = None
    fb.config.date_listed = None
    fb.config.delivery_method = None
    fb.config.availability = None
    fb.config.search_city = ["gothenburg"]
    fb.config.city_name = ["Gothenburg"]
    fb.config.radius = None
    fb.config.currency = None
    fb.config.max_price = None
    fb.config.min_price = None
    fb.config.category = None
    fb.config.monitor_config = None
    fb.page = page_stub or MagicMock()
    fb.translator = lambda x: x
    return fb


def _make_item_config(search_phrases=("RTX 5060",)) -> MagicMock:
    ic = MagicMock()
    ic.name = "gpu"
    ic.search_phrases = list(search_phrases)
    ic.searched_count = 0
    ic.condition = None
    ic.date_listed = None
    ic.delivery_method = None
    ic.availability = None
    ic.search_city = None
    ic.city_name = None
    ic.radius = None
    ic.currency = None
    ic.max_price = None
    ic.min_price = None
    ic.category = None
    ic.keywords = []
    ic.antikeywords = []
    ic.marketplace = "facebook"
    return ic


class FacebookSearchShallowSkipTests(unittest.TestCase):

    def _run_search_collecting_yields(
        self,
        fb: "FacebookMarketplace",
        item_config: MagicMock,
        found_listings: list,
    ) -> list:
        """Drive the generator and collect all yielded listings."""
        return list(fb.search(item_config))

    def _patch_common(self, found_listings: list):
        """Common patches needed to run search() without a real browser."""
        return [
            patch("ai_marketplace_monitor.facebook.FacebookSearchResultPage"),
            patch.object(
                __import__("ai_marketplace_monitor.facebook", fromlist=["counter"]).counter,
                "increment",
            ),
        ]

    def test_flag_off_always_calls_get_listing_details(self) -> None:
        """When AIMM_SHALLOW_STABLE_SKIP is not set, get_listing_details is called for every card."""
        listing = _make_listing()
        fb = _make_fb_marketplace()

        detail_listing = _make_listing()
        detail_listing.condition = "used"
        detail_listing.seller = "TestSeller"
        detail_listing.description = "A great GPU"
        detail_listing.original_price = ""

        with (
            patch.dict("os.environ", {}, clear=False),
            patch("ai_marketplace_monitor.facebook.FacebookSearchResultPage") as mock_serp_cls,
            patch.object(fb, "goto_url"),
            patch.object(fb, "check_listing", return_value=True),
            patch.object(
                fb, "get_listing_details", return_value=(detail_listing, True)
            ) as mock_detail,
            patch(
                "ai_marketplace_monitor.facebook.should_skip_stable_detail_fetch", return_value=True
            ),
        ):

            # Even with helper returning True, flag off means we never check helper.
            os.environ.pop("AIMM_SHALLOW_STABLE_SKIP", None)
            mock_serp_cls.return_value.get_listings.return_value = [listing]
            results = list(fb.search(_make_item_config()))

        mock_detail.assert_called_once()

    def test_flag_on_stable_listing_skips_get_listing_details(self) -> None:
        """When flag on + helper says stable, get_listing_details must NOT be called."""
        import os

        listing = _make_listing()
        fb = _make_fb_marketplace()

        with (
            patch.dict("os.environ", {"AIMM_SHALLOW_STABLE_SKIP": "1"}),
            patch("ai_marketplace_monitor.facebook.FacebookSearchResultPage") as mock_serp_cls,
            patch.object(fb, "goto_url"),
            patch.object(fb, "check_listing", return_value=True),
            patch.object(fb, "get_listing_details") as mock_detail,
            patch(
                "ai_marketplace_monitor.facebook.should_skip_stable_detail_fetch", return_value=True
            ),
        ):

            mock_serp_cls.return_value.get_listings.return_value = [listing]
            results = list(fb.search(_make_item_config()))

        mock_detail.assert_not_called()
        self.assertEqual(results, [])

    def test_flag_on_new_listing_still_calls_get_listing_details(self) -> None:
        """When flag on but helper says NOT stable, get_listing_details must still be called."""
        import os

        listing = _make_listing()
        fb = _make_fb_marketplace()

        detail_listing = _make_listing()
        detail_listing.condition = "used"
        detail_listing.seller = "TestSeller"
        detail_listing.description = "A great GPU"
        detail_listing.original_price = ""

        with (
            patch.dict("os.environ", {"AIMM_SHALLOW_STABLE_SKIP": "1"}),
            patch("ai_marketplace_monitor.facebook.FacebookSearchResultPage") as mock_serp_cls,
            patch.object(fb, "goto_url"),
            patch.object(fb, "check_listing", return_value=True),
            patch.object(
                fb, "get_listing_details", return_value=(detail_listing, True)
            ) as mock_detail,
            patch(
                "ai_marketplace_monitor.facebook.should_skip_stable_detail_fetch",
                return_value=False,
            ),
        ):

            mock_serp_cls.return_value.get_listings.return_value = [listing]
            results = list(fb.search(_make_item_config()))

        mock_detail.assert_called_once()

    def test_flag_on_mixed_batch_only_skips_stable(self) -> None:
        """Two listings: one stable, one new. Only the new one triggers get_listing_details."""
        import os

        stable = _make_listing(url="https://www.facebook.com/marketplace/item/111/")
        new_one = _make_listing(price="4500", url="https://www.facebook.com/marketplace/item/222/")
        fb = _make_fb_marketplace()

        detail_listing = _make_listing(
            price="4500", url="https://www.facebook.com/marketplace/item/222/"
        )
        detail_listing.condition = "used"
        detail_listing.seller = "Seller2"
        detail_listing.description = "Another GPU"
        detail_listing.original_price = ""

        def _should_skip(listing, logger=None):
            return listing.post_url.split("?")[0].endswith("111/")

        with (
            patch.dict("os.environ", {"AIMM_SHALLOW_STABLE_SKIP": "1"}),
            patch("ai_marketplace_monitor.facebook.FacebookSearchResultPage") as mock_serp_cls,
            patch.object(fb, "goto_url"),
            patch.object(fb, "check_listing", return_value=True),
            patch.object(
                fb, "get_listing_details", return_value=(detail_listing, True)
            ) as mock_detail,
            patch(
                "ai_marketplace_monitor.facebook.should_skip_stable_detail_fetch",
                side_effect=_should_skip,
            ),
        ):

            mock_serp_cls.return_value.get_listings.return_value = [stable, new_one]
            results = list(fb.search(_make_item_config()))

        # get_listing_details called exactly once (for the new listing only).
        self.assertEqual(mock_detail.call_count, 1)
        call_url = mock_detail.call_args[0][0]
        self.assertIn("222", call_url)


import os  # noqa: E402 — imported here so test methods above can reference it

if __name__ == "__main__":
    unittest.main()
