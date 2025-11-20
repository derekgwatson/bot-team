"""Page object for Buz quote pages."""
import logging
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


class QuotePage:
    """Represents a Buz quote page with automation methods."""

    def __init__(self, page: Page, config):
        """
        Initialize quote page.

        Args:
            page: Playwright page object
            config: Banji config object
        """
        self.page = page
        self.config = config

    def navigate_to_quote(self, quote_id: str):
        """
        Navigate to a specific quote by ID.

        Args:
            quote_id: The quote identifier (e.g., 'Q-12345')
        """
        # TODO: Update this URL pattern based on actual Buz quote URLs
        # This is a placeholder - you'll need to adjust based on real Buz URLs
        quote_url = f"{self.config.buz_base_url}/quotes/{quote_id}"

        logger.info(f"Navigating to quote: {quote_id}")
        self.page.goto(quote_url, timeout=self.config.buz_navigation_timeout)

        # Wait for page to be ready (adjust selector based on actual Buz UI)
        # TODO: Replace with actual quote page identifier
        self.page.wait_for_load_state("networkidle")
        logger.info(f"Quote page loaded: {quote_id}")

    def get_total_price(self) -> float:
        """
        Extract the total quoted price from the page.

        Returns:
            Total price as a float

        Raises:
            ValueError: If price cannot be extracted or parsed
        """
        # TODO: Update this selector based on actual Buz UI
        # This is a placeholder - you'll need to inspect the actual quote page
        # to find the correct selector for the total price element

        logger.info("Extracting total price")

        try:
            # Example selector - adjust based on actual Buz HTML structure
            # Options: CSS selector, text content, data attributes, etc.
            price_selector = '[data-testid="quote-total"]'  # Placeholder

            price_element = self.page.locator(price_selector)
            price_text = price_element.text_content()

            if not price_text:
                raise ValueError("Price element found but contains no text")

            # Parse price (remove currency symbols, commas, etc.)
            # Example: "$1,234.56" -> 1234.56
            price_clean = price_text.replace('$', '').replace(',', '').strip()
            price = float(price_clean)

            logger.info(f"Total price extracted: {price}")
            return price

        except PlaywrightTimeoutError:
            logger.error("Timeout waiting for price element")
            raise ValueError("Could not find price element on page")
        except (ValueError, AttributeError) as e:
            logger.error(f"Failed to parse price: {e}")
            raise ValueError(f"Could not extract price from page: {e}")

    def open_bulk_edit(self):
        """
        Click the bulk edit button to open bulk edit mode.

        Raises:
            ValueError: If bulk edit button cannot be found or clicked
        """
        logger.info("Opening bulk edit mode")

        try:
            # TODO: Update selector based on actual Buz UI
            # Find and click the bulk edit button
            bulk_edit_button = self.page.locator('button:has-text("Bulk Edit")')  # Placeholder
            bulk_edit_button.click()

            # Wait for bulk edit interface to load
            # TODO: Adjust based on actual UI behavior
            self.page.wait_for_load_state("networkidle")

            logger.info("Bulk edit mode opened")

        except PlaywrightTimeoutError:
            logger.error("Timeout waiting for bulk edit button")
            raise ValueError("Could not find bulk edit button")

    def save_bulk_edit(self):
        """
        Save the bulk edit changes (without making any actual changes).
        This triggers price recalculation.

        Raises:
            ValueError: If save button cannot be found or save fails
        """
        logger.info("Saving bulk edit (triggering price recalculation)")

        try:
            # TODO: Update selector based on actual Buz UI
            save_button = self.page.locator('button:has-text("Save")')  # Placeholder
            save_button.click()

            # Wait for save to complete
            # TODO: Look for success indicator, spinner to disappear, etc.
            self.page.wait_for_load_state("networkidle", timeout=self.config.buz_save_timeout)

            # Optional: wait for success message or updated UI
            # self.page.wait_for_selector('[data-testid="save-success"]')

            logger.info("Bulk edit saved successfully")

        except PlaywrightTimeoutError:
            logger.error("Timeout waiting for save to complete")
            raise ValueError("Save operation timed out")

    def refresh_pricing(self, quote_id: str) -> dict:
        """
        Full workflow: navigate to quote, capture price, bulk edit save, capture new price.

        Args:
            quote_id: The quote identifier

        Returns:
            dict with before/after prices and comparison

        Example:
            {
                'quote_id': 'Q-12345',
                'price_before': 1000.00,
                'price_after': 1200.00,
                'price_changed': True,
                'change_amount': 200.00,
                'change_percent': 20.0
            }
        """
        logger.info(f"Starting price refresh workflow for quote: {quote_id}")

        # Step 1: Navigate to quote
        self.navigate_to_quote(quote_id)

        # Step 2: Get initial price
        price_before = self.get_total_price()
        logger.info(f"Price before refresh: {price_before}")

        # Step 3: Open bulk edit
        self.open_bulk_edit()

        # Step 4: Save (no changes - just trigger recalc)
        self.save_bulk_edit()

        # Step 5: Get updated price
        price_after = self.get_total_price()
        logger.info(f"Price after refresh: {price_after}")

        # Step 6: Calculate differences
        price_changed = abs(price_before - price_after) > 0.01  # Account for float precision
        change_amount = price_after - price_before

        if price_before > 0:
            change_percent = (change_amount / price_before) * 100
        else:
            change_percent = 0.0

        result = {
            'quote_id': quote_id,
            'price_before': round(price_before, 2),
            'price_after': round(price_after, 2),
            'price_changed': price_changed,
            'change_amount': round(change_amount, 2),
            'change_percent': round(change_percent, 2)
        }

        logger.info(f"Price refresh complete: {result}")
        return result
