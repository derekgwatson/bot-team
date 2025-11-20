"""Page object for Buz authentication using storage state."""
import logging
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


# Start URL to verify authentication
BUZ_APP_URL = "https://go.buzmanager.com/Settings/Inventory"


class LoginPage:
    """Handles Buz authentication using Playwright storage state."""

    def __init__(self, page: Page, config, org_config):
        """
        Initialize login page.

        Args:
            page: Playwright page object (already has storage state loaded)
            config: Banji config object (browser settings, timeouts)
            org_config: Organization-specific config (name, storage_state_path)
        """
        self.page = page
        self.config = config
        self.org_config = org_config

    def login(self):
        """
        Verify Buz authentication using storage state.

        The browser context already has the storage state loaded with auth cookies.
        This method just navigates to Buz and verifies we're authenticated.

        Raises:
            ValueError: If authentication fails
        """
        org_name = self.org_config['name']
        logger.info(f"Verifying Buz authentication for organization: {org_name}")

        try:
            # Navigate to Buz app - storage state will handle authentication
            logger.info(f"Navigating to Buz app: {BUZ_APP_URL}")
            self.page.goto(BUZ_APP_URL, timeout=self.config.buz_login_timeout)

            # Wait for page to load - should land in the app (not login page)
            self.page.wait_for_load_state("networkidle", timeout=self.config.buz_login_timeout)

            # Verify we're in the app (not redirected to login)
            current_url = self.page.url
            if "go.buzmanager.com" not in current_url and "mybuz" not in current_url:
                raise ValueError(
                    f"Authentication failed - redirected to: {current_url}\n"
                    f"Storage state may be expired or invalid.\n"
                    f"Run: python tools/buz_auth_bootstrap.py {org_name}"
                )

            # If we landed on org selector, storage state is valid but org selection might be needed
            if "mybuz/organizations" in current_url:
                logger.warning(
                    f"Landed on organization selector page. "
                    f"Storage state may need to be regenerated with org selection.\n"
                    f"Run: python tools/buz_auth_bootstrap.py {org_name}"
                )

            logger.info(f"Authentication successful for {org_name}")
            logger.info(f"Current URL: {current_url}")

        except PlaywrightTimeoutError as e:
            logger.error(f"Authentication timeout for {org_name}: {e}")
            raise ValueError(
                f"Authentication failed - timeout\n"
                f"Storage state may be expired.\n"
                f"Run: python tools/buz_auth_bootstrap.py {org_name}"
            )
        except Exception as e:
            logger.error(f"Authentication failed for {org_name}: {e}")
            raise ValueError(f"Authentication failed: {e}")

    def is_logged_in(self) -> bool:
        """
        Check if currently logged in by checking URL.

        Returns:
            True if in Buz app, False otherwise
        """
        try:
            current_url = self.page.url
            # If we're on go.buzmanager.com, we're authenticated
            return "go.buzmanager.com" in current_url or "console1.buzmanager.com" in current_url
        except:
            return False
