from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from ai_marketplace_monitor.facebook import FacebookRegularItemPage


class _BodyLocator:
    def __init__(self, text: str) -> None:
        self._text = text

    def text_content(self) -> str:
        return self._text


class FacebookTraderaTests(unittest.TestCase):
    @staticmethod
    def _translator(text: str) -> str:
        mapping = {
            "Condition": "Skick",
            "Description": "Beskrivning",
            "Details": "Detaljer",
            "Information about the seller Tradera": "Information om säljaren Tradera",
            "Location is approximate": "Platsen är ungefärlig",
            "See more": "Visa mer",
            "**unspecified**": "**unspecified**",
        }
        return mapping.get(text, text)

    @staticmethod
    def _build_page(text: str) -> MagicMock:
        page = MagicMock()
        page.content.return_value = f"<html><body>{text}</body></html>"

        def locator(selector: str):
            if selector == "body":
                return _BodyLocator(text)
            raise RuntimeError(f"Unexpected locator: {selector}")

        page.locator.side_effect = locator
        return page

    def test_tradera_description_includes_delivery_details(self) -> None:
        text = "\n".join(
            [
                "Mer information från Tradera",
                "Beskrivning",
                "ASUS GeForce RTX 5060 Ti PRIME grafikkort med 16 GB GDDR7-minne och PCIe 5.0-stöd.",
                "Detaljer",
                "Skick",
                "Använd",
                "Leverans",
                "Lokal upphämtning eller leverans för 59,00 kr",
                "Information om säljaren Tradera",
                "elias_72",
            ]
        )
        page = self._build_page(text)

        fb_page = FacebookRegularItemPage(page, self._translator, None)

        self.assertEqual(
            fb_page.get_description(),
            "\n\n".join(
                [
                    "ASUS GeForce RTX 5060 Ti PRIME grafikkort med 16 GB GDDR7-minne och PCIe 5.0-stöd.",
                    "Skick\nAnvänd",
                    "Leverans\nLokal upphämtning eller leverans för 59,00 kr",
                ]
            ),
        )
        self.assertEqual(fb_page.get_condition(), "Använd")

    def test_tradera_detected_from_more_information_header(self) -> None:
        text = "\n".join(
            [
                "Mer information från Tradera",
                "Beskrivning",
                "ASUS GeForce RTX 5060 Ti PRIME grafikkort med 16 GB GDDR7-minne och PCIe 5.0-stöd.",
            ]
        )
        page = self._build_page(text)

        fb_page = FacebookRegularItemPage(page, self._translator, None)
        fb_page.get_seller = MagicMock(return_value="elias_72")

        self.assertTrue(fb_page.check_is_tradera())
        self.assertEqual(
            fb_page.get_description(),
            "ASUS GeForce RTX 5060 Ti PRIME grafikkort med 16 GB GDDR7-minne och PCIe 5.0-stöd.",
        )

    def test_tradera_description_supports_inline_label_and_value(self) -> None:
        text = "\n".join(
            [
                "Mer information från Tradera",
                "Beskrivning ASUS GeForce RTX 5060 Ti PRIME grafikkort med 16 GB GDDR7-minne och PCIe 5.0-stöd.",
                "Skick Ny",
                "Leverans Lokal upphämtning eller leverans för 59,00 kr",
            ]
        )
        page = self._build_page(text)

        fb_page = FacebookRegularItemPage(page, self._translator, None)
        fb_page.get_seller = MagicMock(return_value="elias_72")

        self.assertEqual(
            fb_page.get_description(),
            "\n\n".join(
                [
                    "ASUS GeForce RTX 5060 Ti PRIME grafikkort med 16 GB GDDR7-minne och PCIe 5.0-stöd.",
                    "Skick\nNy",
                    "Leverans\nLokal upphämtning eller leverans för 59,00 kr",
                ]
            ),
        )

    def test_tradera_location_uses_place_block_and_ignores_approximate_label(self) -> None:
        text = "\n".join(
            [
                "Mer information från Tradera",
                "Plats",
                "Storvreta",
                "Plats är ungefärlig",
                "Information om säljaren Tradera",
                "elias_72",
            ]
        )
        page = self._build_page(text)

        fb_page = FacebookRegularItemPage(page, self._translator, None)

        self.assertEqual(fb_page.get_location(), "Storvreta")
