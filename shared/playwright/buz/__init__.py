"""
Buz-specific Playwright utilities.

This module provides common helpers for bots that interact with Buz,
including org configuration, navigation helpers, and concurrency locking.

Usage:
    from shared.playwright.buz import BuzOrgs, BuzNavigation, BuzPlaywrightLock

    # Get org config
    org = BuzOrgs.get_org('canberra')
    storage_path = org['storage_state_path']

    # Navigate to user management
    nav = BuzNavigation(page)
    await nav.go_to_user_management()

    # Use Playwright with lock (prevents concurrent Buz access)
    lock = BuzPlaywrightLock()
    async with lock.acquire_async('ivy'):
        # Only one bot can be in here at a time
        await do_buz_work()
"""

from shared.playwright.buz.orgs import BuzOrgs
from shared.playwright.buz.navigation import BuzNavigation
from shared.playwright.buz.lock import BuzPlaywrightLock, get_buz_lock

__all__ = [
    'BuzOrgs',
    'BuzNavigation',
    'BuzPlaywrightLock',
    'get_buz_lock',
]
