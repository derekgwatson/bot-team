"""
Buz navigation helpers.

Common navigation patterns for Buz-interacting bots.
"""
import logging
from typing import Optional
from playwright.async_api import Page

logger = logging.getLogger(__name__)


class BuzNavigation:
    """
    Provides common navigation helpers for Buz.

    Handles things like the org selector page that can appear
    when navigating to Buz pages.
    """

    # Common Buz URLs
    USER_MANAGEMENT_URL = "https://go.buzmanager.com/Settings/Users"
    HOME_URL = "https://go.buzmanager.com"

    def __init__(self, page: Page, timeout: int = 30000):
        """
        Initialize navigation helper.

        Args:
            page: Playwright page instance
            timeout: Default navigation timeout in milliseconds
        """
        self.page = page
        self.timeout = timeout

    async def handle_org_selector(self) -> bool:
        """
        Check if on org selector page and click through if so.

        Returns:
            True if org selector was handled, False if not on org selector
        """
        if "mybuz/organizations" not in self.page.url:
            return False

        logger.info("On org selector page, clicking through...")

        org_link = self.page.locator('td a').first
        if await org_link.count() > 0:
            await org_link.click()
            await self.page.wait_for_load_state('networkidle')
            logger.info("Clicked through org selector")
            return True
        else:
            raise Exception("On org selector page but couldn't find org link to click")

    async def go_to_user_management(self) -> None:
        """
        Navigate to the user management page.

        Handles the org selector redirect if it appears.
        """
        logger.info("Navigating to user management page...")
        await self.page.goto(self.USER_MANAGEMENT_URL, wait_until='networkidle', timeout=self.timeout)
        logger.info(f"User page loaded at: {self.page.url}")

        # Handle org selector if we landed there
        if await self.handle_org_selector():
            # Re-navigate to user management after org selection
            logger.info("Re-navigating to user management after org selection...")
            await self.page.goto(self.USER_MANAGEMENT_URL, wait_until='networkidle', timeout=self.timeout)

        # Wait for user table
        await self.page.wait_for_selector('table#userListTable', timeout=self.timeout)
        logger.info("User table found")

    async def set_page_size(self, size: int = 500) -> None:
        """
        Set the page size for user listing.

        Args:
            size: Page size (typically 500 for max)
        """
        logger.info(f"Setting page size to {size}...")
        page_size_select = self.page.locator('div.select-editable select')
        await page_size_select.select_option(value=f'6: {size}')
        await self.page.wait_for_timeout(1000)
        logger.info(f"Page size set to {size}")

    async def set_user_filters(
        self,
        is_active: bool,
        user_type: str
    ) -> None:
        """
        Set the active/inactive and employee/customer filters.

        Args:
            is_active: True for active users, False for inactive
            user_type: 'employee' or 'customer'
        """
        # Active/inactive filter (second li in list-inline)
        active_select = self.page.locator('ul.list-inline li:nth-child(2) select')
        active_value = "0: true" if is_active else "1: false"
        await active_select.select_option(value=active_value)
        await self.page.wait_for_timeout(300)

        # Employee/customer filter (third li in list-inline)
        user_type_select = self.page.locator('ul.list-inline li:nth-child(3) select')
        user_type_value = "1: 5" if user_type == "customer" else "0: 0"
        await user_type_select.select_option(value=user_type_value)
        await self.page.wait_for_timeout(500)

    async def search_user(self, email: str) -> None:
        """
        Search for a user by email.

        Types character-by-character to trigger Angular change detection.

        Args:
            email: Email address to search for
        """
        search_input = self.page.locator('input#search-text')
        await search_input.clear()
        await self.page.wait_for_timeout(300)
        await search_input.click()
        await self.page.wait_for_timeout(100)
        await search_input.press_sequentially(email, delay=100)
        # Trigger Angular's input event
        await search_input.dispatch_event('input')
        await self.page.wait_for_timeout(1000)

    async def wait_for_navigation(self, url_pattern: str, timeout: Optional[int] = None) -> None:
        """
        Wait for navigation to a URL matching the pattern.

        Args:
            url_pattern: Substring to match in URL
            timeout: Timeout in milliseconds (uses default if not specified)
        """
        actual_timeout = timeout or self.timeout
        await self.page.wait_for_url(
            lambda url: url_pattern in url,
            timeout=actual_timeout
        )
