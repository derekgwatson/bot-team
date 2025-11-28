"""
Async browser manager for Playwright-based bots.

Provides browser lifecycle management with storage state authentication
for multi-org scenarios like Buz.
"""
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class AsyncBrowserManager:
    """
    Manages Playwright browser lifecycle with async API.

    Supports multi-org scenarios where each org has its own storage state
    for authentication.

    Usage:
        async with AsyncBrowserManager(headless=True) as browser:
            page = await browser.new_page_for_org('canberra', storage_state_path)
            # ... do stuff
    """

    def __init__(
        self,
        headless: bool = True,
        default_timeout: int = 30000,
        screenshot_dir: str = 'screenshots',
        screenshot_on_failure: bool = True
    ):
        """
        Initialize browser manager.

        Args:
            headless: Run browser in headless mode
            default_timeout: Default timeout in milliseconds
            screenshot_dir: Directory for screenshots
            screenshot_on_failure: Take screenshot on exceptions
        """
        self.headless = headless
        self.default_timeout = default_timeout
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_on_failure = screenshot_on_failure

        self.playwright = None
        self.browser: Optional[Browser] = None
        self._contexts: Dict[str, BrowserContext] = {}

    async def __aenter__(self):
        """Context manager entry - launch browser."""
        logger.info(f"Starting browser (headless={self.headless})")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close browser."""
        # Take screenshot on exception if configured
        if exc_type and self.screenshot_on_failure:
            for context_name, context in self._contexts.items():
                for page in context.pages:
                    try:
                        await self._screenshot(page, f"error_{context_name}")
                    except Exception as e:
                        logger.warning(f"Could not take error screenshot: {e}")

        # Close all contexts
        for context in self._contexts.values():
            try:
                await context.close()
            except Exception as e:
                logger.warning(f"Error closing context: {e}")

        self._contexts.clear()

        # Close browser
        if self.browser:
            await self.browser.close()
            self.browser = None

        # Stop playwright
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

        logger.info("Browser closed")
        return False  # Don't suppress exceptions

    async def new_context(
        self,
        name: str,
        storage_state_path: Optional[str] = None
    ) -> BrowserContext:
        """
        Create a new browser context.

        Args:
            name: Name for this context (for tracking)
            storage_state_path: Path to storage state JSON file for auth

        Returns:
            BrowserContext instance
        """
        if not self.browser:
            raise RuntimeError("Browser not started. Use async with AsyncBrowserManager():")

        # Close existing context with same name if exists
        if name in self._contexts:
            await self._contexts[name].close()

        # Build context options
        context_kwargs: Dict[str, Any] = {
            'viewport': {'width': 1920, 'height': 1080}
        }

        if storage_state_path:
            storage_path = Path(storage_state_path)
            if not storage_path.exists():
                raise FileNotFoundError(
                    f"Storage state file not found: {storage_state_path}. "
                    f"Run the auth bootstrap script first."
                )
            logger.info(f"Loading storage state from: {storage_state_path}")
            context_kwargs['storage_state'] = str(storage_path)

        context = await self.browser.new_context(**context_kwargs)
        context.set_default_timeout(self.default_timeout)

        self._contexts[name] = context
        logger.info(f"Created browser context: {name}")

        return context

    async def new_page_for_org(
        self,
        org_name: str,
        storage_state_path: str
    ) -> Page:
        """
        Create a new page for a specific org with its authentication.

        Convenience method that creates a context and page in one call.

        Args:
            org_name: Organization name (used as context name)
            storage_state_path: Path to storage state JSON

        Returns:
            Page instance
        """
        context = await self.new_context(org_name, storage_state_path)
        return await context.new_page()

    async def _screenshot(self, page: Page, name: str) -> Optional[str]:
        """
        Take a screenshot of a page.

        Args:
            page: Page to screenshot
            name: Screenshot name prefix

        Returns:
            Path to saved screenshot or None
        """
        try:
            self.screenshot_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{name}_{timestamp}.png"
            filepath = self.screenshot_dir / filename

            # Use short timeout for screenshots - they're nice-to-have, not critical
            await page.screenshot(path=str(filepath), full_page=True, timeout=10000)
            logger.info(f"Screenshot saved: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return None

    async def screenshot(self, page: Page, name: str = "screenshot") -> Optional[str]:
        """
        Public method to take a screenshot.

        Args:
            page: Page to screenshot
            name: Screenshot name prefix

        Returns:
            Path to saved screenshot or None
        """
        return await self._screenshot(page, name)

    def get_context(self, name: str) -> Optional[BrowserContext]:
        """Get a context by name."""
        return self._contexts.get(name)
