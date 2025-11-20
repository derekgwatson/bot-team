"""Page object for Buz login."""
import logging
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


class LoginPage:
    """Handles Buz authentication."""

    def __init__(self, page: Page, config):
        """
        Initialize login page.

        Args:
            page: Playwright page object
            config: Banji config object
        """
        self.page = page
        self.config = config

    def login(self, username: str = None, password: str = None):
        """
        Login to Buz application.

        Args:
            username: Buz username (defaults to config)
            password: Buz password (defaults to config)

        Raises:
            ValueError: If login fails
        """
        username = username or self.config.buz_username
        password = password or self.config.buz_password

        logger.info(f"Logging into Buz as: {username}")

        try:
            # Navigate to login page
            login_url = f"{self.config.buz_base_url}/login"
            self.page.goto(login_url, timeout=self.config.buz_login_timeout)

            # TODO: Update selectors based on actual Buz login form
            # These are placeholders - inspect actual Buz login page for correct selectors

            # Fill username
            username_input = self.page.locator('input[name="username"]')  # Placeholder
            username_input.fill(username)

            # Fill password
            password_input = self.page.locator('input[name="password"]')  # Placeholder
            password_input.fill(password)

            # Click login button
            login_button = self.page.locator('button[type="submit"]')  # Placeholder
            login_button.click()

            # Wait for successful login (adjust based on actual Buz behavior)
            # Options: wait for redirect, wait for dashboard element, etc.
            self.page.wait_for_load_state("networkidle", timeout=self.config.buz_login_timeout)

            # TODO: Verify successful login
            # Look for a user menu, dashboard element, or check URL changed
            # Example: self.page.wait_for_selector('[data-testid="user-menu"]')

            logger.info("Login successful")

        except PlaywrightTimeoutError as e:
            logger.error(f"Login timeout: {e}")
            raise ValueError(f"Login failed - timeout: {e}")
        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise ValueError(f"Login failed: {e}")

    def is_logged_in(self) -> bool:
        """
        Check if currently logged in.

        Returns:
            True if logged in, False otherwise
        """
        try:
            # TODO: Update based on actual Buz UI
            # Check for element that only appears when logged in
            # Example: user menu, logout button, etc.
            user_indicator = self.page.locator('[data-testid="user-menu"]')  # Placeholder
            return user_indicator.is_visible(timeout=2000)
        except:
            return False
