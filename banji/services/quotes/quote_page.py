"""Page object for Buz quote pages."""
import logging
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


class QuotePage:
    """Represents a Buz quote page with automation methods."""

    def __init__(self, page: Page, config, org_config):
        """
        Initialize quote page.

        Args:
            page: Playwright page object
            config: Banji config object (browser settings, timeouts)
            org_config: Organization-specific config (name, storage_state_path)
        """
        self.page = page
        self.config = config
        self.org_config = org_config

    def navigate_to_quote(self, quote_id: str) -> str:
        """
        Navigate to a specific quote using Quick Lookup.

        Optimization: Checks if Quick Lookup box is already on current page
        before navigating to home page. This saves time when navigating from
        bulk edit or other pages that have the search box.

        Args:
            quote_id: The quote number (e.g., '12345')

        Returns:
            str: The internal orderPkId extracted from the URL

        Raises:
            ValueError: If navigation fails
        """
        logger.info(f"Navigating to quote: {quote_id} (org: {self.org_config['name']})")

        try:
            # Optimization: Check if Quick Lookup is already on current page
            # The #LookupText search box is at the top of most Buz pages
            lookup_input = self.page.locator('#LookupText')

            try:
                # Wait briefly to see if search box is already visible
                if lookup_input.is_visible(timeout=1000):
                    logger.info("Quick Lookup found on current page - using it directly")
                else:
                    raise Exception("Not visible")
            except:
                # Search box not on current page, navigate to home first
                logger.info("Quick Lookup not on current page, navigating to home")
                self.page.goto("https://go.buzmanager.com", timeout=self.config.buz_navigation_timeout)
                self.page.wait_for_load_state("networkidle")

            # Now use the Quick Lookup (either found or just navigated to it)
            lookup_input = self.page.locator('#LookupText')
            lookup_input.fill(quote_id)

            # Press Enter to search
            lookup_input.press('Enter')

            # Wait for navigation to quote summary page
            self.page.wait_for_url(lambda url: 'Sales/Summary' in url, timeout=self.config.buz_navigation_timeout)
            self.page.wait_for_load_state("networkidle")

            # Extract orderPkId from URL
            current_url = self.page.url
            logger.info(f"Quote page loaded: {current_url}")

            # Parse orderPkId from URL: .../Sales/Summary?orderId=9b7b351a-...
            if 'orderId=' not in current_url:
                raise ValueError(f"Could not find orderId in URL: {current_url}")

            order_pk_id = current_url.split('orderId=')[1].split('&')[0]
            logger.info(f"Extracted orderPkId: {order_pk_id}")

            return order_pk_id

        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout navigating to quote {quote_id}: {e}")
            raise ValueError(f"Could not navigate to quote {quote_id} - timeout")
        except Exception as e:
            logger.error(f"Failed to navigate to quote {quote_id}: {e}")
            raise ValueError(f"Could not navigate to quote {quote_id}: {e}")

    def get_total_price(self) -> float:
        """
        Extract the total quoted price from the Summary page.

        Must be on the Sales/Summary page when calling this.

        Returns:
            Total price as a float

        Raises:
            ValueError: If price cannot be extracted or parsed
        """
        logger.info("Extracting total price from summary page")

        try:
            # Find the total cell with bold text and top border
            # Selector targets: <td class="dxtl dxtl__B0" style="font-weight:bold;text-align:Right;border-top:2px solid #CCC !important;">$2,872.34</td>
            price_selector = 'td.dxtl[style*="font-weight:bold"][style*="border-top:2px solid"]'

            price_element = self.page.locator(price_selector).last  # Use .last in case there are multiple
            price_text = price_element.text_content()

            if not price_text:
                raise ValueError("Price element found but contains no text")

            # Parse price (remove currency symbols, commas, etc.)
            # Example: "$2,872.34" -> 2872.34
            price_clean = price_text.replace('$', '').replace(',', '').strip()
            price = float(price_clean)

            logger.info(f"Total price extracted: ${price}")
            return price

        except PlaywrightTimeoutError:
            logger.error("Timeout waiting for price element")
            raise ValueError("Could not find price element on summary page")
        except (ValueError, AttributeError) as e:
            logger.error(f"Failed to parse price: {e}")
            raise ValueError(f"Could not extract price from page: {e}")

    def open_bulk_edit(self, order_pk_id: str):
        """
        Navigate directly to bulk edit page for the order.

        Args:
            order_pk_id: The internal order ID (UUID)

        Raises:
            ValueError: If bulk edit page fails to load
        """
        logger.info(f"Opening bulk edit mode for order: {order_pk_id}")

        try:
            # Navigate directly to bulk edit URL
            bulk_edit_url = f"https://go.buzmanager.com/Sales/BulkEditOrder?orderPkId={order_pk_id}"
            self.page.goto(bulk_edit_url, timeout=self.config.buz_navigation_timeout)

            # Wait for page to load
            self.page.wait_for_load_state("networkidle")

            # Verify we're on the bulk edit page
            if 'BulkEditOrder' not in self.page.url:
                raise ValueError(f"Not on bulk edit page. Current URL: {self.page.url}")

            logger.info("Bulk edit page loaded")

        except PlaywrightTimeoutError:
            logger.error("Timeout loading bulk edit page")
            raise ValueError("Could not load bulk edit page")

    def save_bulk_edit(self):
        """
        Click the Save button on bulk edit page.
        This triggers price recalculation without making any changes.

        Waits intelligently for actual completion indicators rather than arbitrary timeouts:
        - Page navigation away from BulkEditOrder (success)
        - Error messages appearing (failure)
        - Network activity stopping (completion)

        Raises:
            ValueError: If save button cannot be found or save fails
        """
        logger.info("Clicking Save button (triggering price recalculation)")

        try:
            # Record current URL before save
            start_url = self.page.url
            logger.info(f"Starting save from URL: {start_url}")

            # Use configured timeout as our safety net (3 minutes by default)
            max_timeout = self.config.buz_save_timeout
            logger.info(f"Using save timeout: {max_timeout}ms")

            # Click the Save button: <a href="#" id="bulkEditOrderSubmit" ...>
            # Use no_wait_after=True because we'll explicitly wait for completion indicators
            save_button = self.page.locator('#bulkEditOrderSubmit')
            save_button.click(timeout=max_timeout, no_wait_after=True)
            logger.info("Save button clicked, watching for completion...")

            # Wait for EITHER:
            # 1. Page navigates away from BulkEditOrder (typical success case)
            # 2. Network becomes idle (processing complete)
            try:
                # Wait for network to settle
                # This will return when there's no network activity for 500ms
                self.page.wait_for_load_state("networkidle", timeout=max_timeout)
                logger.info("Network activity settled")

                # Check if we're still on bulk edit page or navigated away
                current_url = self.page.url
                if 'BulkEditOrder' not in current_url:
                    logger.info(f"Navigated away from bulk edit to: {current_url}")
                else:
                    logger.info("Still on bulk edit page - checking for error messages")

                    # Look for common error indicators
                    # Buz typically shows errors in .alert or .error-message divs
                    # Note: Avoid broad selectors like [class*="error"] which match
                    # styling classes like "text-error" on buttons
                    error_selectors = [
                        '.alert-danger',
                        '.alert-error',
                        '.error-message',
                        '.validation-error',
                        '.dx-invalid-message',  # DevExpress validation message
                    ]

                    for selector in error_selectors:
                        try:
                            error_elem = self.page.locator(selector).first
                            if error_elem.is_visible(timeout=1000):
                                error_text = error_elem.text_content()
                                logger.error(f"Error message detected: {error_text}")
                                raise ValueError(f"Save failed with error: {error_text}")
                        except PlaywrightTimeoutError:
                            # No error found with this selector, continue checking
                            continue

                    logger.info("No errors detected, save appears successful")

                # Give a moment for any final async operations
                self.page.wait_for_timeout(1000)
                logger.info("Bulk edit save completed successfully")

            except PlaywrightTimeoutError:
                # Network never settled - check what state we're in
                current_url = self.page.url
                logger.warning(f"Timeout waiting for network idle. Current URL: {current_url}")

                # If we're on an error page, that's a failure
                if 'error' in current_url.lower():
                    raise ValueError("Navigated to error page during save")

                # Otherwise, the page might still be processing but functional
                # Check if we can still interact with the page
                try:
                    # Try to get page title as a simple alive check
                    title = self.page.title()
                    logger.warning(f"Page appears responsive (title: {title}) but network still active")
                    # Consider this a success if we're not on an error page
                    logger.info("Proceeding despite network activity")
                except:
                    raise ValueError("Page became unresponsive during save operation")

        except PlaywrightTimeoutError as e:
            logger.error(f"Timeout during save operation: {e}")
            raise ValueError("Save operation timed out - page may still be processing")
        except Exception as e:
            logger.error(f"Failed to save bulk edit: {e}")
            raise ValueError(f"Save operation failed: {e}")

    def refresh_pricing(self, quote_id: str) -> dict:
        """
        Full workflow: navigate to quote, capture price, bulk edit save, capture new price.

        Args:
            quote_id: The quote number (e.g., '12345')

        Returns:
            dict with before/after prices and comparison

        Example:
            {
                'quote_id': '12345',
                'price_before': 1000.00,
                'price_after': 1200.00,
                'price_changed': True,
                'change_amount': 200.00,
                'change_percent': 20.0
            }
        """
        logger.info(f"Starting price refresh workflow for quote: {quote_id}")

        # Step 1: Navigate to quote and get orderPkId
        order_pk_id = self.navigate_to_quote(quote_id)

        # Step 2: Get initial price (already on summary page)
        price_before = self.get_total_price()
        logger.info(f"Price before refresh: ${price_before}")

        # Step 3: Open bulk edit
        self.open_bulk_edit(order_pk_id)

        # Step 4: Save (no changes - just trigger recalc)
        self.save_bulk_edit()

        # Step 5: Navigate back to summary page to get updated price
        summary_url = f"https://go.buzmanager.com/Sales/Summary?orderId={order_pk_id}"
        logger.info(f"Navigating back to summary page: {summary_url}")
        self.page.goto(summary_url, timeout=self.config.buz_navigation_timeout)
        self.page.wait_for_load_state("networkidle")

        # Step 6: Get updated price
        price_after = self.get_total_price()
        logger.info(f"Price after refresh: ${price_after}")

        # Step 7: Calculate differences
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

    def refresh_pricing_batch(self, quote_ids: list) -> dict:
        """
        Refresh pricing for multiple quotes in a single browser session.

        This is more efficient than calling refresh_pricing multiple times
        because the browser stays open between quotes.

        Args:
            quote_ids: List of quote numbers (e.g., ['12345', '12346', '12347'])

        Returns:
            dict with summary and individual results:
            {
                'total_quotes': 3,
                'successful': 2,
                'failed': 1,
                'results': [
                    {
                        'quote_id': '12345',
                        'success': True,
                        'price_before': 1000.00,
                        'price_after': 1200.00,
                        'price_changed': True,
                        'change_amount': 200.00,
                        'change_percent': 20.0
                    },
                    {
                        'quote_id': '12346',
                        'success': False,
                        'error': 'Could not navigate to quote 12346 - timeout'
                    },
                    ...
                ]
            }
        """
        logger.info(f"Starting batch price refresh for {len(quote_ids)} quotes")

        results = []
        successful = 0
        failed = 0

        for i, quote_id in enumerate(quote_ids):
            logger.info(f"Processing quote {i + 1}/{len(quote_ids)}: {quote_id}")

            try:
                result = self.refresh_pricing(quote_id)
                result['success'] = True
                results.append(result)
                successful += 1
                logger.info(f"Quote {quote_id} processed successfully")

            except Exception as e:
                logger.error(f"Failed to process quote {quote_id}: {e}")
                results.append({
                    'quote_id': quote_id,
                    'success': False,
                    'error': str(e)
                })
                failed += 1

        summary = {
            'total_quotes': len(quote_ids),
            'successful': successful,
            'failed': failed,
            'results': results
        }

        logger.info(f"Batch refresh complete: {successful}/{len(quote_ids)} successful")
        return summary
