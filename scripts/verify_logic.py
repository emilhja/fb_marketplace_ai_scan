import os
import sys
from playwright.sync_api import sync_playwright

# Add current dir to path
sys.path.append(os.getcwd())

from ai_marketplace_monitor.facebook import FacebookRegularItemPage
import ai_marketplace_monitor.facebook as fb_mod


def test_listing(url):
    print(f"Testing URL: {url}")
    print(f"DEBUG: fb_mod file: {fb_mod.__file__}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url)
        # Wait for page load
        page.wait_for_timeout(2000)

        fb_page = FacebookRegularItemPage(page, None, None)
        print(f"DEBUG: fb_page methods: {[m for m in dir(fb_page) if not m.startswith('_')]}")

        title = fb_page.get_title()
        availability = fb_page.get_availability()
        is_tradera = fb_page.check_is_tradera()

        print(f"Parsed Title: '{title}'")
        print(f"Availability: {availability}")
        print(f"Is Tradera: {is_tradera}")

        browser.close()


def mock_test_tradera():
    print("Testing Mocked Tradera Content")
    from unittest.mock import MagicMock

    page = MagicMock()
    # Mocking exactly what I saw in the screenshot
    page.content.return_value = """
        <html>
            <div>Mer information från Tradera</div>
            <div role="button">Visa på Tradera</div>
            <h1>Tradera · Some Item Title</h1>
        </html>
    """
    page.query_selector_all.return_value = [
        MagicMock(text_content=lambda: "Tradera · Some Item Title")
    ]

    fb_page = FacebookRegularItemPage(page, None, None)
    fb_page.get_seller = MagicMock(return_value="LasseArre")  # Seller name doesn't have Tradera

    title = fb_page.get_title()
    availability = fb_page.get_availability()
    is_tradera = fb_page.check_is_tradera()

    print(f"Parsed Title: '{title}'")
    print(f"Availability: {availability}")
    print(f"Is Tradera: {is_tradera}")


if __name__ == "__main__":
    mock_test_tradera()
    print("-" * 20)
    # Test the false positive 'Monster dator'
    test_listing("https://www.facebook.com/marketplace/item/1391366728972596/")
    # ...
