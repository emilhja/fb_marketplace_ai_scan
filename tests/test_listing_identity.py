from __future__ import annotations

from unittest import TestCase

from ai_marketplace_monitor.listing import Listing
from ai_marketplace_monitor.pg_cache import (
    extract_marketplace_listing_id,
    listing_key_from_listing,
    normalize_url,
)


class ListingIdentityTests(TestCase):
    def test_extract_listing_id_from_marketplace_url(self) -> None:
        listing_id = extract_marketplace_listing_id(
            "https://www.facebook.com/marketplace/item/123456789/?ref=search"
        )
        self.assertEqual(listing_id, "123456789")

    def test_fallback_to_normalized_url_hash_key(self) -> None:
        listing_id = extract_marketplace_listing_id(
            "https://www.facebook.com/marketplace/something/weird?tracking=1",
            fallback_id="",
        )
        self.assertTrue(listing_id.startswith("url:"))

    def test_listing_key_uses_marketplace_and_stable_id(self) -> None:
        listing = Listing(
            marketplace="facebook",
            name="gpu",
            id="ignored",
            title="RTX 5060",
            image="",
            price="5000",
            post_url="https://www.facebook.com/marketplace/item/42/?foo=bar",
            location="Gothenburg",
            seller="Seller",
            condition="used",
            description="desc",
        )
        self.assertEqual(
            normalize_url(listing.post_url), "https://www.facebook.com/marketplace/item/42/"
        )
        self.assertEqual(listing_key_from_listing(listing), "facebook:42")
