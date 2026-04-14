from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from ai_marketplace_monitor.facebook import FacebookRegularItemPage


class _FakeElement:
    def __init__(self, text: str, parent: "_FakeElement | None" = None) -> None:
        self._text = text
        self._parent = parent

    def text_content(self) -> str:
        return self._text

    def query_selector(self, selector: str):
        if selector == "xpath=..":
            return self._parent
        return None


class _FakeLocator:
    def __init__(self, element: _FakeElement) -> None:
        self._element = element

    def element_handle(self) -> _FakeElement:
        return self._element


class FacebookLocationTests(unittest.TestCase):
    @staticmethod
    def _translator(text: str) -> str:
        mapping = {
            "Location is approximate": "Platsen är ungefärlig",
            "See more": "Visa mer",
        }
        return mapping.get(text, text)

    def test_extracts_location_from_multiline_approximate_block(self) -> None:
        page = MagicMock()
        container = _FakeElement("Gislaved, F\nPlatsen är ungefärlig")
        page.locator.return_value = _FakeLocator(container)

        fb_page = FacebookRegularItemPage(page, self._translator, None)

        self.assertEqual(fb_page.get_location(), "Gislaved, F")

    def test_extracts_location_when_label_shares_same_line(self) -> None:
        page = MagicMock()
        container = _FakeElement("Gislaved, F Platsen är ungefärlig")
        page.locator.return_value = _FakeLocator(container)

        fb_page = FacebookRegularItemPage(page, self._translator, None)

        self.assertEqual(fb_page.get_location(), "Gislaved, F")
