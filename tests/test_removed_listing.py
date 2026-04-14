"""Tests for removed-listing detection on Marketplace item pages."""

from __future__ import annotations

from ai_marketplace_monitor.facebook import build_removed_listing


class _FakePage:
    def __init__(self, html: str) -> None:
        self._html = html

    def content(self) -> str:
        return self._html


def test_build_removed_listing_detects_swedish_message() -> None:
    listing = build_removed_listing(
        _FakePage("<html><body>Det här inlägget finns inte längre</body></html>"),
        "https://www.facebook.com/marketplace/item/12345?ref=foo",
        translator=lambda text: text,
    )

    assert listing is not None
    assert listing.id == "12345"
    assert listing.availability == "Borttagen"
    assert listing.post_url.endswith("?ref=foo")


def test_build_removed_listing_returns_none_for_live_page() -> None:
    listing = build_removed_listing(
        _FakePage("<html><body>Vanlig annons</body></html>"),
        "https://www.facebook.com/marketplace/item/12345",
        translator=lambda text: text,
    )

    assert listing is None
