"""
Shared Playwright infrastructure for bot-team.

This module provides common Playwright utilities for browser automation bots.
Currently supports async Playwright for bots that interact with Buz.

Usage:
    from shared.playwright import AsyncBrowserManager
    from shared.playwright.buz import BuzOrgs, BuzNavigation

    async with AsyncBrowserManager(headless=True) as browser:
        page = await browser.new_page_for_org('canberra')
        # ... do stuff
"""

from shared.playwright.async_browser import AsyncBrowserManager

__all__ = [
    'AsyncBrowserManager',
]
