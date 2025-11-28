"""
Browser service for downloading inventory and pricing exports from Buz.

Uses Playwright to automate the export process through Buz's web interface.
Uses BuzPlaywrightLock to prevent concurrent access from multiple bots.
"""
import logging
import asyncio
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
from playwright.async_api import Page, Download

from shared.playwright.async_browser import AsyncBrowserManager
from shared.playwright.buz import get_buz_lock

logger = logging.getLogger(__name__)


class BuzExportService:
    """
    Service for exporting inventory and pricing data from Buz.

    Handles browser automation to navigate to export pages, select options,
    and download Excel files.
    """

    def __init__(
        self,
        config,
        headless: bool = True,
        download_dir: Optional[str] = None
    ):
        """
        Initialize the export service.

        Args:
            config: Bot configuration object
            headless: Run browser in headless mode
            download_dir: Directory to save downloaded files (defaults to temp)
        """
        self.config = config
        self.headless = headless
        self.download_dir = Path(download_dir) if download_dir else Path(tempfile.gettempdir())
        self.download_dir.mkdir(parents=True, exist_ok=True)

    async def export_inventory(
        self,
        org_key: str,
        include_inactive: bool = True
    ) -> Dict[str, Any]:
        """
        Export inventory items from Buz for a specific organization.

        Args:
            org_key: Organization key to export from
            include_inactive: Include inactive items in export

        Returns:
            Dict with file_path to downloaded Excel, groups exported, etc.
        """
        org_config = self.config.get_org_config(org_key)
        storage_state_path = org_config['storage_state_path']

        logger.info(f"Starting inventory export for {org_key}")

        # Acquire Buz lock to prevent concurrent access from other bots
        buz_lock = get_buz_lock()
        async with buz_lock.acquire_async('ivy'):
            async with AsyncBrowserManager(
                headless=self.headless,
                screenshot_dir=self.config.browser_screenshot_dir,
                default_timeout=self.config.buz_navigation_timeout
            ) as browser:
                page = await browser.new_page_for_org(org_key, storage_state_path)

                try:
                    # Navigate to inventory export page
                    await page.goto(self.config.buz_inventory_url)
                    logger.info(f"Navigated to inventory import page")

                    # Wait for page to load and handle org selector if present
                    await self._handle_org_selector(page, org_key)

                    # Get available inventory groups
                    groups = await self._get_inventory_groups(page)
                    logger.info(f"Found {len(groups)} inventory groups")

                    if not groups:
                        return {
                            'success': False,
                            'error': 'No inventory groups found',
                            'org_key': org_key
                        }

                    # Click the export link to open modal
                    await page.click('a[href="#exportModal"]')
                    await page.wait_for_selector('#exportModal.in, #exportModal.show', timeout=5000)
                    logger.info("Opened export modal")

                    # Check include inactive checkbox if requested
                    if include_inactive:
                        checkbox = page.locator('#includeNotCurrent')
                        if await checkbox.count() > 0:
                            if not await checkbox.is_checked():
                                await checkbox.click()
                                logger.info("Enabled include inactive items")

                    # Select all options in the inventory group select
                    select = page.locator('#inventoryGroupCodes')
                    await select.wait_for(state='visible')

                    # Select all options
                    await self._select_all_options(page, '#inventoryGroupCodes')
                    logger.info("Selected all inventory groups")

                    # Click export button and wait for download
                    file_path = await self._click_export_and_download(
                        page,
                        org_key,
                        'inventory'
                    )

                    return {
                        'success': True,
                        'file_path': str(file_path),
                        'org_key': org_key,
                        'groups': groups,
                        'include_inactive': include_inactive
                    }

                except Exception as e:
                    logger.exception(f"Error exporting inventory for {org_key}: {e}")
                    await browser.screenshot(page, f"error_inventory_{org_key}")
                    return {
                        'success': False,
                        'error': str(e),
                        'org_key': org_key
                    }

    async def export_pricing(
        self,
        org_key: str,
        include_inactive: bool = True
    ) -> Dict[str, Any]:
        """
        Export pricing coefficients from Buz for a specific organization.

        Args:
            org_key: Organization key to export from
            include_inactive: Include inactive pricing in export

        Returns:
            Dict with file_path to downloaded Excel, groups exported, etc.
        """
        org_config = self.config.get_org_config(org_key)
        storage_state_path = org_config['storage_state_path']

        logger.info(f"Starting pricing export for {org_key}")

        # Acquire Buz lock to prevent concurrent access from other bots
        buz_lock = get_buz_lock()
        async with buz_lock.acquire_async('ivy'):
            async with AsyncBrowserManager(
                headless=self.headless,
                screenshot_dir=self.config.browser_screenshot_dir,
                default_timeout=self.config.buz_navigation_timeout
            ) as browser:
                page = await browser.new_page_for_org(org_key, storage_state_path)

                try:
                    # Navigate to pricing export page
                    await page.goto(self.config.buz_pricing_url)
                    logger.info(f"Navigated to pricing import page")

                    # Wait for page to load and handle org selector if present
                    await self._handle_org_selector(page, org_key)

                    # Get available pricing groups
                    groups = await self._get_pricing_groups(page)
                    logger.info(f"Found {len(groups)} pricing groups")

                    if not groups:
                        return {
                            'success': False,
                            'error': 'No pricing groups found',
                            'org_key': org_key
                        }

                    # Click the export link to open modal
                    await page.click('a[href="#exportModal"]')
                    await page.wait_for_selector('#exportModal.in, #exportModal.show', timeout=5000)
                    logger.info("Opened export modal")

                    # Check include inactive checkbox if requested
                    if include_inactive:
                        checkbox = page.locator('#includeNotCurrent')
                        if await checkbox.count() > 0:
                            if not await checkbox.is_checked():
                                await checkbox.click()
                                logger.info("Enabled include inactive pricing")

                    # Select all options in the pricing group select
                    select = page.locator('#InventoryGroupPkIdList')
                    await select.wait_for(state='visible')

                    # Select all options
                    await self._select_all_options(page, '#InventoryGroupPkIdList')
                    logger.info("Selected all pricing groups")

                    # Click export button and wait for download
                    file_path = await self._click_export_and_download(
                        page,
                        org_key,
                        'pricing'
                    )

                    return {
                        'success': True,
                        'file_path': str(file_path),
                        'org_key': org_key,
                        'groups': groups,
                        'include_inactive': include_inactive
                    }

                except Exception as e:
                    logger.exception(f"Error exporting pricing for {org_key}: {e}")
                    await browser.screenshot(page, f"error_pricing_{org_key}")
                    return {
                        'success': False,
                        'error': str(e),
                        'org_key': org_key
                    }

    async def _handle_org_selector(self, page: Page, org_key: str) -> None:
        """
        Handle the org selector page if it appears.

        Some Buz pages redirect to an org selector when multiple orgs are available.
        """
        try:
            # Check if org selector is present (common pattern in Buz)
            org_selector = page.locator('select[name="orgCode"], .org-selector')
            if await org_selector.count() > 0:
                logger.info("Org selector detected, selecting organization")
                # Try to select the org or click through
                await org_selector.select_option(value=org_key, timeout=3000)
                # Wait for navigation
                await page.wait_for_load_state('networkidle', timeout=10000)
        except Exception:
            # Org selector may not be present, that's fine
            pass

    async def _get_inventory_groups(self, page: Page) -> List[Dict[str, str]]:
        """
        Get available inventory groups from the page.

        Returns list of dicts with group_code and group_name.
        """
        groups = []
        try:
            # First try to find groups from the export modal
            await page.click('a[href="#exportModal"]')
            await page.wait_for_selector('#exportModal.in, #exportModal.show', timeout=5000)

            select = page.locator('#inventoryGroupCodes')
            await select.wait_for(state='visible', timeout=5000)

            options = await select.locator('option').all()
            for option in options:
                value = await option.get_attribute('value')
                text = await option.text_content()
                if value and text:
                    groups.append({
                        'group_code': value,
                        'group_name': text.strip()
                    })

            # Close modal
            await page.keyboard.press('Escape')

        except Exception as e:
            logger.warning(f"Could not get inventory groups: {e}")

        return groups

    async def _get_pricing_groups(self, page: Page) -> List[Dict[str, str]]:
        """
        Get available pricing groups from the page.

        Returns list of dicts with group_code and group_name.
        """
        groups = []
        try:
            # First try to find groups from the export modal
            await page.click('a[href="#exportModal"]')
            await page.wait_for_selector('#exportModal.in, #exportModal.show', timeout=5000)

            select = page.locator('#InventoryGroupPkIdList')
            await select.wait_for(state='visible', timeout=5000)

            options = await select.locator('option').all()
            for option in options:
                value = await option.get_attribute('value')
                text = await option.text_content()
                if value and text:
                    groups.append({
                        'group_code': value,
                        'group_name': text.strip()
                    })

            # Close modal
            await page.keyboard.press('Escape')

        except Exception as e:
            logger.warning(f"Could not get pricing groups: {e}")

        return groups

    async def _select_all_options(self, page: Page, select_id: str) -> None:
        """
        Select all options in a multi-select element.

        Args:
            page: Playwright page
            select_id: CSS selector for the select element
        """
        # Get all option values
        options = await page.locator(f'{select_id} option').all()
        values = []
        for option in options:
            value = await option.get_attribute('value')
            if value:
                values.append(value)

        # Use JavaScript to select all options (more reliable for multi-select)
        if values:
            await page.evaluate(f'''
                const select = document.querySelector("{select_id}");
                if (select) {{
                    Array.from(select.options).forEach(opt => opt.selected = true);
                }}
            ''')

    async def _click_export_and_download(
        self,
        page: Page,
        org_key: str,
        export_type: str
    ) -> Path:
        """
        Click the export button and wait for the download.

        Args:
            page: Playwright page
            org_key: Organization key
            export_type: 'inventory' or 'pricing'

        Returns:
            Path to the downloaded file
        """
        # Set up download handler
        async with page.expect_download(timeout=self.config.buz_download_timeout) as download_info:
            # Click export button
            await page.click('#btnExport')
            logger.info("Clicked export button, waiting for download...")

        download: Download = await download_info.value

        # Save to our download directory with meaningful name
        filename = f"buz_{export_type}_{org_key}_{download.suggested_filename}"
        file_path = self.download_dir / filename
        await download.save_as(str(file_path))

        logger.info(f"Downloaded {export_type} export to: {file_path}")
        return file_path

    async def get_available_groups(
        self,
        org_key: str,
        group_type: str = 'inventory'
    ) -> Dict[str, Any]:
        """
        Get available groups for an org without downloading.

        Args:
            org_key: Organization key
            group_type: 'inventory' or 'pricing'

        Returns:
            Dict with groups list
        """
        org_config = self.config.get_org_config(org_key)
        storage_state_path = org_config['storage_state_path']

        # Acquire Buz lock to prevent concurrent access from other bots
        buz_lock = get_buz_lock()
        async with buz_lock.acquire_async('ivy'):
            async with AsyncBrowserManager(
                headless=self.headless,
                screenshot_dir=self.config.browser_screenshot_dir,
                default_timeout=self.config.buz_navigation_timeout
            ) as browser:
                page = await browser.new_page_for_org(org_key, storage_state_path)

                try:
                    if group_type == 'inventory':
                        await page.goto(self.config.buz_inventory_url)
                        await self._handle_org_selector(page, org_key)
                        groups = await self._get_inventory_groups(page)
                    else:
                        await page.goto(self.config.buz_pricing_url)
                        await self._handle_org_selector(page, org_key)
                        groups = await self._get_pricing_groups(page)

                    return {
                        'success': True,
                        'org_key': org_key,
                        'group_type': group_type,
                        'groups': groups
                    }

                except Exception as e:
                    logger.exception(f"Error getting {group_type} groups for {org_key}: {e}")
                    return {
                        'success': False,
                        'error': str(e),
                        'org_key': org_key
                    }


def run_async(coro):
    """Run an async coroutine from sync code."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)
