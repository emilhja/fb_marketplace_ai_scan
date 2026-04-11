"""Tests for utils.extract_price (locale-aware normalization)."""

from __future__ import annotations

import unittest

from ai_marketplace_monitor.utils import extract_price, parse_listing_prices


class ExtractPriceTests(unittest.TestCase):
    def test_swedish_space_thousands(self) -> None:
        self.assertEqual(extract_price("3 500 kr"), "3500")
        self.assertEqual(extract_price("12 999 kr"), "12999")
        self.assertEqual(extract_price("1 234 567 SEK"), "1234567")

    def test_swedish_current_and_strikethrough_second_ignored(self) -> None:
        """Facebook often concatenates current price and original in one scrape."""
        self.assertEqual(extract_price("10 000 17 999 kr"), "10000")
        self.assertEqual(extract_price("10 000 kr 17 999 kr"), "10000")

    def test_parse_listing_prices_original_when_two_swedish_amounts(self) -> None:
        self.assertEqual(parse_listing_prices("10 000 17 999 kr"), ("10000", "17999"))
        self.assertEqual(parse_listing_prices("10 000 kr 17 999 kr"), ("10000", "17999"))

    def test_parse_listing_prices_single_amount(self) -> None:
        self.assertEqual(parse_listing_prices("3 500 kr"), ("3500", ""))
        self.assertEqual(parse_listing_prices("500 - 600 kr"), ("500", ""))

    def test_us_dollar(self) -> None:
        self.assertEqual(extract_price("$1,234.56"), "1234.56")
        self.assertEqual(extract_price("$3,500"), "3500")

    def test_european_comma_decimal(self) -> None:
        self.assertEqual(extract_price("1.234,5 €"), "1234.5")
        self.assertEqual(extract_price("12,99 kr"), "12.99")

    def test_range_returns_first_amount(self) -> None:
        self.assertEqual(extract_price("500 - 600 kr"), "500")
        self.assertEqual(extract_price("100 – 200"), "100")

    def test_unspecified_passthrough(self) -> None:
        self.assertEqual(extract_price("**unspecified**"), "**unspecified**")

    def test_empty_passthrough(self) -> None:
        self.assertEqual(extract_price(""), "")

    def test_legacy_pipe_split_repair(self) -> None:
        self.assertEqual(extract_price("3 | 500"), "3500")


if __name__ == "__main__":
    unittest.main()
