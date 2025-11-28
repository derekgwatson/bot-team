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
from hugo.database.db import user_db

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
        self.debug = getattr(config, 'browser_debug', False)

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
        logger.info(f"Storage state path: {org_config['storage_state_path']}")
        logger.info(f"Headless mode: {self.headless}")

        all_users = []

        logger.info("Creating AsyncBrowserManager...")
        async with AsyncBrowserManager(
            headless=self.headless,
            screenshot_dir=self.config.browser_screenshot_dir,
            screenshot_on_failure=self.config.browser_screenshot_on_failure
        ) as browser:
            logger.info("Browser started, creating page for org...")
            page = await browser.new_page_for_org(
                org_key,
                org_config['storage_state_path']
            )
            logger.info("Page created, initializing navigation...")

            nav = BuzNavigation(page, timeout=self.config.buz_navigation_timeout, debug=self.debug)

            # Navigate to user management
            logger.info("Navigating to user management...")
            await nav.go_to_user_management()

            # Set page size to maximum
            logger.info("Setting page size...")
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

            nav = BuzNavigation(page, timeout=self.config.buz_navigation_timeout, debug=self.debug)

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

            nav = BuzNavigation(page, timeout=self.config.buz_navigation_timeout, debug=self.debug)

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

    async def check_auth_health(self, org_key: str) -> Dict[str, Any]:
        """
        Check if auth is still valid for an org.

        Tries to load the user management page and checks if we get
        redirected to a login page.

        Args:
            org_key: Organization key

        Returns:
            Dict with status ('healthy', 'expired', 'failed') and details
        """
        org_config = self.config.get_org_config(org_key)

        result = {
            'org_key': org_key,
            'status': 'failed',
            'message': ''
        }

        try:
            async with AsyncBrowserManager(
                headless=True,  # Always headless for health checks
                screenshot_dir=self.config.browser_screenshot_dir,
                screenshot_on_failure=False  # Don't screenshot for health checks
            ) as browser:
                page = await browser.new_page_for_org(
                    org_key,
                    org_config['storage_state_path']
                )

                # Try to load the user management page
                await page.goto(
                    BuzNavigation.USER_MANAGEMENT_URL,
                    wait_until='networkidle',
                    timeout=30000
                )

                current_url = page.url.lower()

                # Check if we're on a login page
                if 'login' in current_url or 'signin' in current_url or 'auth' in current_url:
                    result['status'] = 'expired'
                    result['message'] = 'Session expired - redirected to login page'
                elif 'mybuz/organizations' in current_url:
                    # On org selector - that's fine, auth is still valid
                    result['status'] = 'healthy'
                    result['message'] = 'Auth valid (on org selector)'
                elif 'settings/users' in current_url:
                    # Made it to user management
                    result['status'] = 'healthy'
                    result['message'] = 'Auth valid'
                else:
                    # Unknown page - check for common auth failure indicators
                    content = await page.content()
                    if 'sign in' in content.lower() or 'log in' in content.lower():
                        result['status'] = 'expired'
                        result['message'] = f'Session expired - login form detected on {current_url}'
                    else:
                        result['status'] = 'healthy'
                        result['message'] = f'Auth valid (landed on {current_url})'

        except FileNotFoundError as e:
            result['status'] = 'failed'
            result['message'] = f'Storage state file not found: {str(e)}'
        except Exception as e:
            result['status'] = 'failed'
            result['message'] = f'Check failed: {str(e)}'
            logger.exception(f"Auth health check failed for {org_key}")

        return result

    async def check_all_auth_health(self) -> List[Dict[str, Any]]:
        """
        Check auth health for all configured orgs.

        Returns:
            List of health check results
        """
        results = []
        for org_key in self.config.available_orgs:
            result = await self.check_auth_health(org_key)
            results.append(result)
        return results

    # -------------------------------------------------------------------------
    # User Edit Methods
    # -------------------------------------------------------------------------

    async def get_user_details(
        self,
        org_key: str,
        email: str
    ) -> Dict[str, Any]:
        """
        Get editable user details from Buz.

        Args:
            org_key: Organization key
            email: User's email address

        Returns:
            Dict with user details and available_groups, or error
        """
        org_config = self.config.get_org_config(org_key)

        result = {
            'success': False,
            'email': email,
            'org_key': org_key,
            'details': None,
            'available_groups': [],
            'message': ''
        }

        try:
            async with AsyncBrowserManager(
                headless=self.headless,
                screenshot_dir=self.config.browser_screenshot_dir,
                screenshot_on_failure=self.config.browser_screenshot_on_failure
            ) as browser:
                page = await browser.new_page_for_org(
                    org_key,
                    org_config['storage_state_path']
                )

                nav = BuzNavigation(page, timeout=self.config.buz_navigation_timeout, debug=self.debug)

                # Navigate to user edit page
                user_exists = await nav.go_to_user_edit(email)
                if not user_exists:
                    result['message'] = f"User not found: {email}"
                    return result

                # Get details and available groups
                details = await nav.get_user_edit_details()
                groups = await nav.get_available_groups()

                result['success'] = True
                result['details'] = details
                result['available_groups'] = groups
                result['message'] = 'User details retrieved'

        except Exception as e:
            result['message'] = f"Error: {str(e)}"
            logger.exception(f"Error getting user details for {email} in {org_key}")

        return result

    async def update_user(
        self,
        org_key: str,
        email: str,
        changes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update user details in Buz.

        Args:
            org_key: Organization key
            email: User's email address
            changes: Dict with optional keys:
                - group: New group name
                - first_name, last_name, phone, mobile: Field updates
                - customer_name, customer_pkid: Customer assignment

        Returns:
            Dict with success status and message
        """
        org_config = self.config.get_org_config(org_key)

        result = {
            'success': False,
            'email': email,
            'org_key': org_key,
            'changes_applied': [],
            'message': ''
        }

        try:
            async with AsyncBrowserManager(
                headless=self.headless,
                screenshot_dir=self.config.browser_screenshot_dir,
                screenshot_on_failure=self.config.browser_screenshot_on_failure
            ) as browser:
                page = await browser.new_page_for_org(
                    org_key,
                    org_config['storage_state_path']
                )

                nav = BuzNavigation(page, timeout=self.config.buz_navigation_timeout, debug=self.debug)

                # Navigate to user edit page
                user_exists = await nav.go_to_user_edit(email)
                if not user_exists:
                    result['message'] = f"User not found: {email}"
                    return result

                # Apply changes
                if 'group' in changes:
                    if await nav.update_user_group(changes['group']):
                        result['changes_applied'].append(f"group -> {changes['group']}")

                if 'customer_name' in changes and 'customer_pkid' in changes:
                    if await nav.update_user_customer(
                        changes['customer_name'],
                        changes['customer_pkid']
                    ):
                        result['changes_applied'].append(
                            f"customer -> {changes['customer_name']}"
                        )

                # Update basic fields
                await nav.update_user_fields(
                    first_name=changes.get('first_name'),
                    last_name=changes.get('last_name'),
                    phone=changes.get('phone'),
                    mobile=changes.get('mobile')
                )

                for field in ['first_name', 'last_name', 'phone', 'mobile']:
                    if field in changes:
                        result['changes_applied'].append(f"{field} -> {changes[field]}")

                # Save
                if result['changes_applied']:
                    await nav.save_user()
                    result['success'] = True
                    result['message'] = f"Updated: {', '.join(result['changes_applied'])}"

                    # Update local database cache immediately
                    db_updates = {}
                    if 'group' in changes:
                        db_updates['user_group'] = changes['group']
                    if 'first_name' in changes or 'last_name' in changes:
                        # Reconstruct full name from changes
                        first = changes.get('first_name', '')
                        last = changes.get('last_name', '')
                        if first or last:
                            db_updates['full_name'] = f"{first} {last}".strip()

                    if db_updates:
                        db_result = user_db.update_user_fields(
                            email=email,
                            org_key=org_key,
                            **db_updates
                        )
                        if db_result.get('success'):
                            logger.info(f"Updated local cache for {email}: {db_updates}")
                        else:
                            logger.warning(f"Failed to update local cache: {db_result.get('error')}")
                else:
                    result['message'] = "No changes to apply"

        except Exception as e:
            result['message'] = f"Error: {str(e)}"
            logger.exception(f"Error updating user {email} in {org_key}")

        return result

    async def get_available_groups(self, org_key: str) -> Dict[str, Any]:
        """
        Get list of available user groups for an org.

        Uses a dummy user lookup to get the group dropdown options.

        Args:
            org_key: Organization key

        Returns:
            Dict with groups list or error
        """
        org_config = self.config.get_org_config(org_key)

        result = {
            'success': False,
            'org_key': org_key,
            'groups': [],
            'message': ''
        }

        try:
            async with AsyncBrowserManager(
                headless=self.headless,
                screenshot_dir=self.config.browser_screenshot_dir,
                screenshot_on_failure=self.config.browser_screenshot_on_failure
            ) as browser:
                page = await browser.new_page_for_org(
                    org_key,
                    org_config['storage_state_path']
                )

                nav = BuzNavigation(page, timeout=self.config.buz_navigation_timeout, debug=self.debug)

                # Navigate to new user page to get group options
                await page.goto(
                    BuzNavigation.USER_INVITE_URL,
                    wait_until='networkidle',
                    timeout=self.config.buz_navigation_timeout
                )
                await nav.handle_org_selector()

                groups = await nav.get_available_groups()

                result['success'] = True
                result['groups'] = groups
                result['message'] = f"Found {len(groups)} groups"

        except Exception as e:
            result['message'] = f"Error: {str(e)}"
            logger.exception(f"Error getting groups for {org_key}")

        return result

    # -------------------------------------------------------------------------
    # Customer Search Methods
    # -------------------------------------------------------------------------

    async def search_customers(
        self,
        org_key: str,
        query: str
    ) -> Dict[str, Any]:
        """
        Search for customers by company name.

        Args:
            org_key: Organization key
            query: Company name to search for

        Returns:
            Dict with customers list or error
        """
        org_config = self.config.get_org_config(org_key)

        result = {
            'success': False,
            'org_key': org_key,
            'customers': [],
            'message': ''
        }

        try:
            async with AsyncBrowserManager(
                headless=self.headless,
                screenshot_dir=self.config.browser_screenshot_dir,
                screenshot_on_failure=self.config.browser_screenshot_on_failure
            ) as browser:
                page = await browser.new_page_for_org(
                    org_key,
                    org_config['storage_state_path']
                )

                nav = BuzNavigation(page, timeout=self.config.buz_navigation_timeout, debug=self.debug)

                # Navigate to customers and search
                await nav.go_to_customers()
                customers = await nav.search_customer(query)

                # Get PKIDs for each customer
                for customer in customers:
                    if customer['customer_code']:
                        pkid = await nav.get_customer_pkid(customer['customer_code'])
                        customer['customer_pkid'] = pkid or ''

                result['success'] = True
                result['customers'] = customers
                result['message'] = f"Found {len(customers)} customers"

        except Exception as e:
            result['message'] = f"Error: {str(e)}"
            logger.exception(f"Error searching customers in {org_key}")

        return result

    async def get_customer_from_user(
        self,
        org_key: str,
        email: str
    ) -> Dict[str, Any]:
        """
        Get customer details from an existing user's assignment.

        Useful for finding the customer when adding another user to same customer.

        Args:
            org_key: Organization key
            email: Email of existing user

        Returns:
            Dict with customer_name, customer_pkid or error
        """
        org_config = self.config.get_org_config(org_key)

        result = {
            'success': False,
            'org_key': org_key,
            'email': email,
            'customer_name': None,
            'customer_pkid': None,
            'message': ''
        }

        try:
            async with AsyncBrowserManager(
                headless=self.headless,
                screenshot_dir=self.config.browser_screenshot_dir,
                screenshot_on_failure=self.config.browser_screenshot_on_failure
            ) as browser:
                page = await browser.new_page_for_org(
                    org_key,
                    org_config['storage_state_path']
                )

                nav = BuzNavigation(page, timeout=self.config.buz_navigation_timeout, debug=self.debug)

                # Get user details which includes customer info
                user_exists = await nav.go_to_user_edit(email)
                if not user_exists:
                    result['message'] = f"User not found: {email}"
                    return result

                details = await nav.get_user_edit_details()

                customer_name = details.get('customer_name', '')
                customer_pkid = details.get('customer_pkid', '')

                if not customer_name:
                    result['message'] = f"User {email} is not linked to a customer"
                    return result

                # If we have name but not PKID, try to find it
                if customer_name and not customer_pkid:
                    await nav.go_to_customers()
                    customers = await nav.search_customer(customer_name)
                    if customers:
                        pkid = await nav.get_customer_pkid(customers[0]['customer_code'])
                        customer_pkid = pkid or ''

                result['success'] = True
                result['customer_name'] = customer_name
                result['customer_pkid'] = customer_pkid
                result['message'] = f"Found customer: {customer_name}"

        except Exception as e:
            result['message'] = f"Error: {str(e)}"
            logger.exception(f"Error getting customer from user {email} in {org_key}")

        return result

    # -------------------------------------------------------------------------
    # Group Sync Methods
    # -------------------------------------------------------------------------

    async def sync_groups(self, org_key: str) -> Dict[str, Any]:
        """
        Sync groups from Buz to local database.

        Scrapes the groups page and stores results in DB.

        Args:
            org_key: Organization key

        Returns:
            Dict with success status and counts
        """
        org_config = self.config.get_org_config(org_key)

        result = {
            'success': False,
            'org_key': org_key,
            'groups_synced': 0,
            'message': ''
        }

        try:
            async with AsyncBrowserManager(
                headless=self.headless,
                screenshot_dir=self.config.browser_screenshot_dir,
                screenshot_on_failure=self.config.browser_screenshot_on_failure
            ) as browser:
                page = await browser.new_page_for_org(
                    org_key,
                    org_config['storage_state_path']
                )

                nav = BuzNavigation(page, timeout=self.config.buz_navigation_timeout, debug=self.debug)

                # Navigate to groups page and scrape
                await nav.go_to_groups()
                groups = await nav.scrape_groups()

                # Store in database
                db_result = user_db.bulk_upsert_groups(org_key, groups)

                result['success'] = True
                result['groups_synced'] = db_result.get('total', 0)
                result['message'] = f"Synced {result['groups_synced']} groups"
                logger.info(f"Synced groups for {org_key}: {result['groups_synced']} groups")

        except Exception as e:
            result['message'] = f"Error: {str(e)}"
            logger.exception(f"Error syncing groups for {org_key}")

        return result

    async def sync_all_groups(self) -> Dict[str, Any]:
        """
        Sync groups for all configured organizations.

        Returns:
            Dict with results per org
        """
        results = {}
        for org_key in self.config.available_orgs:
            results[org_key] = await self.sync_groups(org_key)
        return results


# Helper function to run async code from sync context
def run_async(coro):
    """
    Run an async coroutine from sync code.

    Handles cases where an event loop may already be running
    (e.g., in some Flask configurations).
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - safe to use asyncio.run()
        logger.debug("No running event loop, using asyncio.run()")
        return asyncio.run(coro)
    else:
        # There's already a running loop - need to run in a separate thread
        import concurrent.futures
        logger.debug("Event loop already running, using thread pool")
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
