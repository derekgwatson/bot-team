"""Browser lifecycle management for Banji."""
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages Playwright browser lifecycle with storage state authentication."""

    def __init__(self, config, org_config=None, headless=None):
        """
        Initialize browser manager.

        Args:
            config: Banji config object with browser settings
            org_config: Optional org-specific config with storage_state_path
            headless: Override headless setting (None uses config default)
        """
        self.config = config
        self.org_config = org_config
        # Allow per-request override of headless mode
        self.headless = headless if headless is not None else config.browser_headless
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def start(self):
        """Start browser and create new page with storage state if provided."""
        logger.info(f"Starting browser (headless={self.headless})")

        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(
            headless=self.headless
        )

        # Create context with storage state if provided (for authentication)
        context_kwargs = {
            'viewport': {'width': 1920, 'height': 1080}
        }

        if self.org_config and 'storage_state_path' in self.org_config:
            storage_state_path = self.org_config['storage_state_path']
            logger.info(f"Loading storage state from: {storage_state_path}")
            context_kwargs['storage_state'] = storage_state_path

        self.context = self.browser.new_context(**context_kwargs)

        # Set default timeout
        self.context.set_default_timeout(self.config.browser_default_timeout)

        self.page = self.context.new_page()
        logger.info("Browser started successfully")

        return self.page

    def screenshot(self, name=None):
        """
        Take a screenshot of the current page.

        Args:
            name: Optional screenshot name (default: timestamp)

        Returns:
            Path to saved screenshot
        """
        if not self.page:
            logger.warning("Cannot take screenshot - no active page")
            return None

        # Create screenshots directory if it doesn't exist
        screenshot_dir = Path(self.config.browser_screenshot_dir)
        screenshot_dir.mkdir(exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if name:
            filename = f"{name}_{timestamp}.png"
        else:
            filename = f"screenshot_{timestamp}.png"

        filepath = screenshot_dir / filename

        try:
            self.page.screenshot(path=str(filepath), full_page=True)
            logger.info(f"Screenshot saved: {filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return None

    def close(self):
        """Close browser and cleanup resources."""
        logger.info("Closing browser")

        if self.context:
            self.context.close()
            self.context = None

        if self.browser:
            self.browser.close()
            self.browser = None

        if self.playwright:
            self.playwright.stop()
            self.playwright = None

        self.page = None
        logger.info("Browser closed")

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup."""
        # Take screenshot on exception if configured
        if exc_type and self.config.browser_screenshot_on_failure:
            self.screenshot("error")

        # In headed mode, pause for debugging before closing
        if not self.headless and self.page:
            logger.info("Headed mode: pausing for inspection. Press 'Resume' in Playwright Inspector to continue.")
            try:
                self.page.pause()
            except Exception as e:
                logger.warning(f"Could not pause: {e}")

        self.close()
        return False  # Don't suppress exceptions
