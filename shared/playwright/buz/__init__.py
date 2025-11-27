"""
Buz-specific Playwright utilities.

This module provides common helpers for bots that interact with Buz,
including org configuration and navigation helpers.

Usage:
    from shared.playwright.buz import BuzOrgs, BuzNavigation

    # Get org config
    org = BuzOrgs.get_org('canberra')
    storage_path = org['storage_state_path']

    # Navigate to user management
    nav = BuzNavigation(page)
    await nav.go_to_user_management()
"""

from shared.playwright.buz.orgs import BuzOrgs
from shared.playwright.buz.navigation import BuzNavigation

__all__ = [
    'BuzOrgs',
    'BuzNavigation',
]
