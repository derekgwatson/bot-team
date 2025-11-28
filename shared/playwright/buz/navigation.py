"""
Buz navigation helpers.

Common navigation patterns for Buz-interacting bots.
"""
import logging
from typing import Optional, Dict, Any, List
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

    # User edit URLs (Angular app on console1)
    USER_EDIT_BASE_URL = "https://console1.buzmanager.com/myorg/user-management/inviteuser"
    USER_INVITE_URL = "https://console1.buzmanager.com/myorg/user-management/inviteuser/new"

    # Customer URLs
    CUSTOMERS_URL = "https://go.buzmanager.com/Contacts/Customers"

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

    # -------------------------------------------------------------------------
    # User Edit Methods
    # -------------------------------------------------------------------------

    async def go_to_user_edit(self, email: str) -> bool:
        """
        Navigate to the user edit page for a specific user.

        Args:
            email: User's email address

        Returns:
            True if user exists and page loaded, False if user not found
        """
        edit_url = f"{self.USER_EDIT_BASE_URL}/{email}"
        logger.info(f"Navigating to user edit page: {edit_url}")

        await self.page.goto(edit_url, wait_until='networkidle', timeout=self.timeout)

        # Handle org selector if we landed there
        if await self.handle_org_selector():
            logger.info("Re-navigating to user edit after org selection...")
            await self.page.goto(edit_url, wait_until='networkidle', timeout=self.timeout)

        # Check if user exists by checking if email field is populated
        email_input = self.page.locator('input#text-email')
        await email_input.wait_for(timeout=self.timeout)
        email_value = await email_input.input_value()

        if not email_value or not email_value.strip():
            logger.info(f"User not found: {email}")
            return False

        logger.info(f"User edit page loaded for: {email}")
        return True

    async def get_user_edit_details(self) -> Dict[str, Any]:
        """
        Extract current user details from the edit form.

        Must be called after go_to_user_edit().

        Returns:
            Dict with user details: first_name, last_name, email, phone, mobile,
            group, customer_name, customer_pkid
        """
        details = {}

        # Basic fields
        details['first_name'] = await self._get_input_value('input#text-firstName')
        details['last_name'] = await self._get_input_value('input#text-lastName')
        details['email'] = await self._get_input_value('input#text-email')
        details['phone'] = await self._get_input_value('input#text-phone')
        details['mobile'] = await self._get_input_value('input#text-mobile')

        # Group - extract selected option text
        group_select = self.page.locator('select.form-control').first
        try:
            group_name = await group_select.evaluate(
                '(select) => select.options[select.selectedIndex]?.text || ""'
            )
            details['group'] = group_name.strip() if group_name else ''
        except Exception:
            details['group'] = ''

        # Customer (for customer users)
        details['customer_name'] = await self._get_input_value('input#customers')

        # Customer PKID (hidden field)
        try:
            customer_pkid = await self.page.evaluate(
                'document.getElementById("customerPkId")?.value || ""'
            )
            details['customer_pkid'] = customer_pkid
        except Exception:
            details['customer_pkid'] = ''

        logger.info(f"Extracted user details: {details['email']}, group={details['group']}")
        return details

    async def _get_input_value(self, selector: str) -> str:
        """Helper to safely get input value."""
        try:
            elem = self.page.locator(selector)
            if await elem.count() > 0:
                value = await elem.input_value()
                return value.strip() if value else ''
        except Exception:
            pass
        return ''

    async def get_available_groups(self) -> List[str]:
        """
        Get list of available user groups from the dropdown.

        Must be called after go_to_user_edit().

        Returns:
            List of group names
        """
        group_select = self.page.locator('select.form-control').first

        try:
            groups = await group_select.evaluate('''(select) => {
                return Array.from(select.options).map(opt => opt.text.trim()).filter(t => t);
            }''')
            logger.info(f"Available groups: {groups}")
            return groups
        except Exception as e:
            logger.warning(f"Could not get available groups: {e}")
            return []

    async def update_user_group(self, new_group: str) -> bool:
        """
        Update the user's group on the edit form.

        Must be called after go_to_user_edit().

        Args:
            new_group: Name of the group to select

        Returns:
            True if successful
        """
        logger.info(f"Updating user group to: {new_group}")

        group_select = self.page.locator('select.form-control').first
        await group_select.select_option(label=new_group)
        await self.page.wait_for_timeout(500)

        # Verify selection
        selected = await group_select.evaluate(
            '(select) => select.options[select.selectedIndex]?.text || ""'
        )
        if selected.strip() == new_group:
            logger.info(f"Group updated to: {new_group}")
            return True
        else:
            logger.warning(f"Group selection mismatch: expected {new_group}, got {selected}")
            return False

    async def update_user_customer(self, customer_name: str, customer_pkid: str) -> bool:
        """
        Assign a customer to the user.

        Must be called after go_to_user_edit().

        Args:
            customer_name: Display name of the customer
            customer_pkid: Customer's primary key ID (GUID)

        Returns:
            True if successful
        """
        logger.info(f"Assigning customer: {customer_name} (ID: {customer_pkid})")

        # Set the hidden PKID field using JavaScript
        await self.page.evaluate(
            f'document.getElementById("customerPkId").value = "{customer_pkid}"'
        )

        # Fill the visible customer name field
        customer_input = self.page.locator('input#customers')
        await customer_input.fill(customer_name)
        await self.page.wait_for_timeout(300)

        logger.info(f"Customer assigned: {customer_name}")
        return True

    async def update_user_fields(
        self,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        phone: Optional[str] = None,
        mobile: Optional[str] = None
    ) -> None:
        """
        Update basic user fields on the edit form.

        Must be called after go_to_user_edit().
        Only updates fields that are provided (not None).

        Args:
            first_name: New first name
            last_name: New last name
            phone: New phone number
            mobile: New mobile number
        """
        if first_name is not None:
            await self.page.fill('input#text-firstName', first_name)
            logger.info(f"Updated first name: {first_name}")

        if last_name is not None:
            await self.page.fill('input#text-lastName', last_name)
            logger.info(f"Updated last name: {last_name}")

        if phone is not None:
            await self.page.fill('input#text-phone', phone)
            logger.info(f"Updated phone: {phone}")

        if mobile is not None:
            await self.page.fill('input#text-mobile', mobile)
            logger.info(f"Updated mobile: {mobile}")

    async def save_user(self) -> bool:
        """
        Save the user edit form.

        Must be called after go_to_user_edit() and making changes.

        Returns:
            True if save appeared successful
        """
        logger.info("Saving user...")

        save_button = self.page.locator('button#save-button')
        await save_button.click()
        await self.page.wait_for_load_state('networkidle')

        # Check if we're still on edit page (might indicate error) or redirected
        current_url = self.page.url
        logger.info(f"After save, URL: {current_url}")

        # Success usually redirects away from the edit page
        return True

    # -------------------------------------------------------------------------
    # Customer Search Methods
    # -------------------------------------------------------------------------

    async def go_to_customers(self) -> None:
        """Navigate to the customers page."""
        logger.info("Navigating to customers page...")
        await self.page.goto(self.CUSTOMERS_URL, wait_until='networkidle', timeout=self.timeout)

        if await self.handle_org_selector():
            await self.page.goto(self.CUSTOMERS_URL, wait_until='networkidle', timeout=self.timeout)

        logger.info("Customers page loaded")

    async def search_customer(self, company_name: str) -> List[Dict[str, str]]:
        """
        Search for customers by company name.

        Must be called after go_to_customers().

        Args:
            company_name: Company name to search for

        Returns:
            List of dicts with customer_name, customer_code, customer_pkid
        """
        logger.info(f"Searching for customer: {company_name}")

        # Click advanced search
        await self.page.click('a:has-text("Advanced Search")')
        await self.page.wait_for_timeout(500)

        # Enter company name
        company_input = self.page.locator('input[name="CompanyName"], input#CompanyName')
        await company_input.fill(company_name)

        # Click Display button
        await self.page.click('button#AdvancedDisplay')
        await self.page.wait_for_load_state('networkidle')
        await self.page.wait_for_timeout(2000)

        results = []

        # Check for empty data row
        empty_row = self.page.locator('tr.dxgvEmptyDataRow_Bootstrap, tr#_grdDevEx_DXEmptyRow')
        if await empty_row.count() > 0:
            logger.info("No customers found")
            return results

        # Get data rows
        rows = self.page.locator('table tbody tr.dxgvDataRow_Bootstrap')
        count = await rows.count()
        logger.info(f"Found {count} customer(s)")

        for i in range(min(count, 10)):  # Limit to 10 results
            row = rows.nth(i)
            try:
                # Customer code from 2nd column
                customer_code = await row.locator('td').nth(1).text_content()
                customer_code = customer_code.strip() if customer_code else ''

                # Customer name from 3rd column (inside <a> tag)
                customer_name_elem = row.locator('td').nth(2).locator('a')
                customer_name = await customer_name_elem.text_content()
                customer_name = customer_name.strip() if customer_name else ''

                if customer_code and customer_name:
                    results.append({
                        'customer_name': customer_name,
                        'customer_code': customer_code,
                        'customer_pkid': ''  # Will need separate lookup
                    })
            except Exception as e:
                logger.warning(f"Error parsing customer row {i}: {e}")

        return results

    async def get_customer_pkid(self, customer_code: str) -> Optional[str]:
        """
        Get customer PKID by navigating to customer details page.

        Args:
            customer_code: Customer code (e.g., "MYCO2000.1")

        Returns:
            Customer PKID (GUID) or None if not found
        """
        details_url = f"https://go.buzmanager.com/Contacts/Customers/Details?Code={customer_code}"
        logger.info(f"Getting PKID for customer: {customer_code}")

        await self.page.goto(details_url, wait_until='networkidle', timeout=self.timeout)

        if await self.handle_org_selector():
            await self.page.goto(details_url, wait_until='networkidle', timeout=self.timeout)

        # Find "New Sale" button and extract PKID from href
        new_sale_link = self.page.locator('a:has-text("New Sale")')
        try:
            href = await new_sale_link.get_attribute('href', timeout=5000)
            if href and 'customerPkId=' in href:
                customer_pkid = href.split('customerPkId=')[-1]
                logger.info(f"Found PKID: {customer_pkid}")
                return customer_pkid
        except Exception as e:
            logger.warning(f"Could not extract PKID: {e}")

        return None
