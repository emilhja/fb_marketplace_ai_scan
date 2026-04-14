from __future__ import annotations

from unittest.mock import MagicMock

from ai_marketplace_monitor.facebook import FacebookSearchResultPage


class _FakeImage:
    def __init__(self, src: str) -> None:
        self._src = src

    def get_attribute(self, name: str) -> str:
        if name != "src":
            raise AssertionError(f"Unexpected image attribute: {name}")
        return self._src


class _FakeAnchor:
    def __init__(self, href: str, text: str) -> None:
        self._href = href
        self._text = text

    def get_attribute(self, name: str) -> str:
        if name != "href":
            raise AssertionError(f"Unexpected anchor attribute: {name}")
        return self._href

    def query_selector_all(self, selector: str) -> list[object]:
        if selector != ":scope > :first-child > div":
            raise AssertionError(f"Unexpected anchor selector: {selector}")
        return []

    def text_content(self) -> str:
        return self._text


class _FakeListing:
    def __init__(self, href: str, text: str, image_src: str) -> None:
        self._anchor = _FakeAnchor(href, text)
        self._image = _FakeImage(image_src)
        self._text = text

    def query_selector(self, selector: str):
        if selector == "a[href*='/marketplace/item/']":
            return self._anchor
        if selector == "img":
            return self._image
        return None

    def text_content(self) -> str:
        return self._text


def test_extract_serp_text_fields_uses_price_title_location_lines() -> None:
    raw_price, title, location = FacebookSearchResultPage._extract_serp_text_fields(
        "3 500 kr\nMSI GeForce RTX 5060ti Ventus 2X OC 8GB\nGöteborg, O"
    )

    assert raw_price == "3 500 kr"
    assert title == "MSI GeForce RTX 5060ti Ventus 2X OC 8GB"
    assert location == "Göteborg, O"


def test_handles_to_listings_falls_back_when_structured_divs_are_missing() -> None:
    page = MagicMock()
    fb_page = FacebookSearchResultPage(page, lambda text: text, None)
    listing = _FakeListing(
        href="/marketplace/item/123456789/?ref=search",
        text="3 500 kr\nMSI GeForce RTX 5060ti Ventus 2X OC 8GB\nGöteborg, O",
        image_src="/images/example.jpg",
    )

    listings = fb_page._handles_to_listings([listing])

    assert len(listings) == 1
    assert listings[0].post_url == "https://www.facebook.com/marketplace/item/123456789/?ref=search"
    assert listings[0].price == "3500"
    assert listings[0].title == "MSI GeForce RTX 5060ti Ventus 2X OC 8GB"
    assert listings[0].location == "Göteborg, O"
    assert listings[0].image == "https://www.facebook.com/images/example.jpg"
