"""Regression tests for stable listing hashing."""

from __future__ import annotations

from ai_marketplace_monitor.listing import Listing


def _listing(image: str, post_url: str) -> Listing:
    return Listing(
        marketplace="facebook",
        name="gpu",
        id="42",
        title="RTX 5060 Ti",
        image=image,
        price="5000",
        post_url=post_url,
        location="Stockholm",
        seller="Seller",
        condition="used",
        description="16 GB card",
    )


def test_listing_hash_ignores_image_and_query_string() -> None:
    a = _listing(
        "https://cdn.example.com/1.jpg", "https://www.facebook.com/marketplace/item/42?ref=foo"
    )
    b = _listing(
        "https://cdn.example.com/2.jpg", "https://www.facebook.com/marketplace/item/42?ref=bar"
    )

    assert a.hash == b.hash
