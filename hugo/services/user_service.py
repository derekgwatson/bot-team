"""
Buz user management service.

Handles scraping users from Buz and toggling their active status.
Uses the shared Playwright infrastructure.
"""
import asyncio
import logging
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from playwright.async_api import Page

from shared.playwright import AsyncBrowserManager
from shared.playwright.buz import BuzOrgs, BuzNavigation

logger = logging.getLogger(__name__)


@dataclass
class BuzUser:
    """Represents a Buz user."""
    full_name: str
    email: str
    mfa_enabled: bool
    group: str
    last_session: str
    is_active: bool
    user_type: str  # 'employee' or 'customer'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'full_name': self.full_name,
            'email': self.email,
            'mfa_enabled': self.mfa_enabled,
            'group': self.group,
            'last_session': self.last_session,
            'is_active': self.is_active,
            'user_type': self.user_type
        }


class BuzUserService:
    """
    Service for managing Buz users.

    Provides methods to scrape users from Buz and toggle their active status.
    """

    def __init__(self, config):
        """
        Initialize user service.

        Args:
            config: Hugo config object with buz_orgs
        """
        self.config = config
        self.headless = config.browser_headless

    async def _scrape_users_from_page(
        self,
        page: Page,
        is_active: bool,
        user_type: str
    ) -> List[BuzUser]:
        """
        Scrape users from the current page state.

        Args:
            page: Playwright page
            is_active: Whether filtering for active users
            user_type: 'employee' or 'customer'

        Returns:
            List of BuzUser objects
        """
        users = []

        # Wait for table
        await page.wait_for_selector('table#userListTable tbody', timeout=10000)

        rows = await page.locator('table#userListTable tbody tr').all()

        for row in rows:
            try:
                # Full Name (in <a> tag within first td)
                full_name_elem = row.locator('td:nth-child(1) a')
                full_name = await full_name_elem.text_content() if await full_name_elem.count() > 0 else ""
                full_name = full_name.strip()

                # Email (second td)
                email_elem = row.locator('td:nth-child(2)')
                email = await email_elem.text_content() if await email_elem.count() > 0 else ""
                email = email.strip()

                # MFA (third td - check for checkmark icon)
                mfa_elem = row.locator('td:nth-child(3) i.fa-check')
                mfa_enabled = await mfa_elem.count() > 0

                # Group (fourth td - text inside badge span)
                group_elem = row.locator('td:nth-child(4) span.badge')
                group = await group_elem.text_content() if await group_elem.count() > 0 else ""
                group = group.strip()

                # Last Session (fifth td)
                last_session_elem = row.locator('td:nth-child(5)')
                last_session = await last_session_elem.text_content() if await last_session_elem.count() > 0 else ""
                last_session = last_session.strip()

                # Skip empty rows
                if not email:
                    continue

                users.append(BuzUser(
                    full_name=full_name,
                    email=email,
                    mfa_enabled=mfa_enabled,
                    group=group,
                    last_session=last_session,
                    is_active=is_active,
                    user_type=user_type
                ))

            except Exception as e:
                logger.warning(f"Error parsing user row: {e}")
                continue

        return users

    async def scrape_org_users(
        self,
        org_key: str,
        progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Scrape all users for an organization.

        Args:
            org_key: Organization key
            progress_callback: Optional callback(message) for progress updates

        Returns:
            Dict with users list and metadata
        """
        org_config = self.config.get_org_config(org_key)
        start_time = time.time()

        def log(msg):
            logger.info(msg)
            if progress_callback:
                progress_callback(msg)

        log(f"Starting sync for {org_config['display_name']}")

        all_users = []

        async with AsyncBrowserManager(
            headless=self.headless,
            screenshot_dir=self.config.browser_screenshot_dir,
            screenshot_on_failure=self.config.browser_screenshot_on_failure
        ) as browser:
            page = await browser.new_page_for_org(
                org_key,
                org_config['storage_state_path']
            )

            nav = BuzNavigation(page, timeout=self.config.buz_navigation_timeout)

            # Navigate to user management
            await nav.go_to_user_management()

            # Set page size to maximum
            await nav.set_page_size(500)

            # Determine combinations to scrape based on org
            if BuzOrgs.has_customers(org_key):
                combinations = [
                    (True, 'employee'),
                    (False, 'employee'),
                    (True, 'customer'),
                    (False, 'customer'),
                ]
            else:
                combinations = [
                    (True, 'employee'),
                    (False, 'employee'),
                ]

            for is_active, user_type in combinations:
                status_text = "Active" if is_active else "Inactive"
                type_text = "Employees" if user_type == "employee" else "Customers"
                log(f"Fetching {status_text} {type_text}...")

                await nav.set_user_filters(is_active, user_type)
                await page.wait_for_timeout(1000)  # Wait for table to update

                users = await self._scrape_users_from_page(page, is_active, user_type)
                all_users.extend(users)
                log(f"  Found {len(users)} {status_text.lower()} {type_text.lower()}")

        duration = time.time() - start_time
        log(f"Sync complete: {len(all_users)} users in {duration:.1f}s")

        return {
            'org_key': org_key,
            'org_name': org_config['display_name'],
            'users': [u.to_dict() for u in all_users],
            'user_count': len(all_users),
            'duration_seconds': duration
        }

    async def toggle_user_status(
        self,
        org_key: str,
        email: str,
        current_is_active: bool,
        user_type: str
    ) -> Dict[str, Any]:
        """
        Toggle a user's active/inactive status in Buz.

        Args:
            org_key: Organization key
            email: User's email address
            current_is_active: Current active status (from cache)
            user_type: 'employee' or 'customer'

        Returns:
            Dict with success status and new state
        """
        org_config = self.config.get_org_config(org_key)

        result = {
            'success': False,
            'email': email,
            'org_key': org_key,
            'new_state': None,
            'message': ''
        }

        async with AsyncBrowserManager(
            headless=self.headless,
            screenshot_dir=self.config.browser_screenshot_dir,
            screenshot_on_failure=self.config.browser_screenshot_on_failure
        ) as browser:
            page = await browser.new_page_for_org(
                org_key,
                org_config['storage_state_path']
            )

            nav = BuzNavigation(page, timeout=self.config.buz_navigation_timeout)

            try:
                await nav.go_to_user_management()
                await nav.set_user_filters(current_is_active, user_type)
                await nav.search_user(email)

                # Find the toggle checkbox
                toggle_checkbox = page.locator(f'input.onoffswitch-checkbox[id="{email}"]')

                if await toggle_checkbox.count() == 0:
                    # Try opposite state (cache might be stale)
                    logger.info(f"User {email} not found in expected state, checking opposite...")
                    await nav.set_user_filters(not current_is_active, user_type)
                    await nav.search_user(email)

                    if await toggle_checkbox.count() == 0:
                        result['message'] = f"User not found in either active or inactive state"
                        return result

                    # Found in opposite state - already in desired state
                    result['success'] = True
                    result['new_state'] = not current_is_active
                    result['message'] = f"User already {'active' if result['new_state'] else 'inactive'} (cache was stale)"
                    return result

                # Verify current state
                actual_is_active = await toggle_checkbox.is_checked()
                if actual_is_active != current_is_active:
                    result['message'] = f"State mismatch: expected {current_is_active}, got {actual_is_active}"
                    return result

                # Click the toggle label
                toggle_label = page.locator(f'label.onoffswitch-label[for="{email}"]')
                await toggle_label.click()
                await page.wait_for_timeout(1000)

                # Verify by checking opposite filter
                await nav.set_user_filters(not current_is_active, user_type)
                await nav.search_user(email)

                if await toggle_checkbox.count() > 0:
                    result['success'] = True
                    result['new_state'] = not current_is_active
                    result['message'] = f"User is now {'active' if result['new_state'] else 'inactive'}"
                else:
                    result['message'] = "Toggle failed - user did not move to opposite state"

            except Exception as e:
                result['message'] = f"Error: {str(e)}"
                logger.exception(f"Error toggling user {email} in {org_key}")

        return result

    async def batch_toggle_users(
        self,
        org_key: str,
        user_changes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Toggle multiple users' status efficiently.

        Reuses browser context for all toggles in same org.

        Args:
            org_key: Organization key
            user_changes: List of {email, is_active, user_type}

        Returns:
            List of result dicts
        """
        org_config = self.config.get_org_config(org_key)
        results = []

        async with AsyncBrowserManager(
            headless=self.headless,
            screenshot_dir=self.config.browser_screenshot_dir,
            screenshot_on_failure=self.config.browser_screenshot_on_failure
        ) as browser:
            page = await browser.new_page_for_org(
                org_key,
                org_config['storage_state_path']
            )

            nav = BuzNavigation(page, timeout=self.config.buz_navigation_timeout)

            try:
                await nav.go_to_user_management()

                for change in user_changes:
                    email = change['email']
                    is_active = change['is_active']
                    user_type = change['user_type']

                    result = {
                        'email': email,
                        'org_key': org_key,
                        'success': False,
                        'new_state': None,
                        'message': ''
                    }

                    try:
                        await nav.set_user_filters(is_active, user_type)
                        await nav.search_user(email)

                        toggle_checkbox = page.locator(f'input.onoffswitch-checkbox[id="{email}"]')

                        if await toggle_checkbox.count() == 0:
                            # Check opposite state
                            await nav.set_user_filters(not is_active, user_type)
                            await nav.search_user(email)

                            if await toggle_checkbox.count() == 0:
                                result['message'] = "User not found"
                                results.append(result)
                                continue

                            # Already in desired state
                            result['success'] = True
                            result['new_state'] = not is_active
                            result['message'] = "Already in target state"
                            results.append(result)
                            continue

                        # Toggle
                        toggle_label = page.locator(f'label.onoffswitch-label[for="{email}"]')
                        await toggle_label.click()
                        await page.wait_for_timeout(1000)

                        # Verify
                        await nav.set_user_filters(not is_active, user_type)
                        await nav.search_user(email)

                        if await toggle_checkbox.count() > 0:
                            result['success'] = True
                            result['new_state'] = not is_active
                            result['message'] = f"Now {'active' if result['new_state'] else 'inactive'}"
                        else:
                            result['message'] = "Toggle verification failed"

                    except Exception as e:
                        result['message'] = f"Error: {str(e)}"
                        logger.exception(f"Error toggling {email}")

                    results.append(result)

            except Exception as e:
                logger.exception(f"Batch toggle error for {org_key}")
                # Mark remaining as failed
                for change in user_changes:
                    if not any(r['email'] == change['email'] for r in results):
                        results.append({
                            'email': change['email'],
                            'org_key': org_key,
                            'success': False,
                            'new_state': None,
                            'message': f"Org-level error: {str(e)}"
                        })

        return results


# Helper function to run async code from sync context
def run_async(coro):
    """Run an async coroutine from sync code."""
    # Use asyncio.run() which properly handles cleanup, including
    # allowing pending tasks to complete before closing the loop.
    # This prevents "Connection closed while reading from the driver"
    # errors from Playwright.
    return asyncio.run(coro)
