"""
Bootstrap Buz authentication for Banji using Playwright storage state.

This tool helps you authenticate to each Buz organization and save the session
to a storage state file. Banji will then use these files to maintain authenticated
sessions without needing passwords.

Usage:
    python tools/buz_auth_bootstrap.py designer_drapes
    python tools/buz_auth_bootstrap.py canberra
    python tools/buz_auth_bootstrap.py tweed

This creates storage state files:
    .secrets/buz_storage_state_designer_drapes.json
    .secrets/buz_storage_state_canberra.json
    .secrets/buz_storage_state_tweed.json
"""
from __future__ import annotations
import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright


START_URL = "https://go.buzmanager.com/Settings/Inventory"  # lands you in the app after login


async def main(org_name: str = "default") -> None:
    """
    Bootstrap Buz authentication for a specific organization.

    Args:
        org_name: Organization name (e.g., 'designer_drapes', 'canberra')
    """
    # Determine where to save the storage state
    # Use banji/.secrets/ directory
    script_dir = Path(__file__).parent.parent  # banji/
    secrets_dir = script_dir / ".secrets"
    secrets_dir.mkdir(parents=True, exist_ok=True)

    state_path = secrets_dir / f"buz_storage_state_{org_name}.json"

    print("\n" + "="*80)
    print(f"Buz Authentication Bootstrap for: {org_name}")
    print("="*80)
    print(f"Storage state will be saved to: {state_path.resolve()}")
    print("="*80 + "\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # show window for manual auth
        ctx = await browser.new_context(accept_downloads=True)
        page = await ctx.new_page()

        # Go to app; it will bounce to identity login automatically
        await page.goto(START_URL)

        print(f">>> Step 1: Log in to Buz")
        print(f">>> Use the credentials for: {org_name}")
        print(">>> Complete MFA if prompted")
        print(">>> (A browser window has opened)")

        # Wait for login to complete - could land on org selector OR directly in app
        print("\n>>> Waiting for login to complete...")
        await page.wait_for_url(
            lambda url: url.startswith("https://go.buzmanager.com/") or "mybuz/organizations" in url,
            timeout=120_000
        )

        # Check if we landed on org selector
        if "mybuz/organizations" in page.url:
            print("\n" + "="*80)
            print(f">>> Step 2: SELECT THE ORGANIZATION for '{org_name}'")
            print("="*80)
            print(">>> You're on the organization selector page.")
            print(f">>> CLICK THE CORRECT ORGANIZATION for {org_name} in the browser")
            print(">>> (This ensures this storage state is tied to the correct org)")
            print("="*80)

            # Wait until they've selected an org and are in the app
            await page.wait_for_url(
                lambda url: url.startswith("https://go.buzmanager.com/"),
                timeout=120_000
            )
            print("\n✓ Organization selected! Continuing...")

        # Navigate to user management to capture console authentication
        print("\n" + "="*80)
        print(">>> Step 3: CAPTURE CONSOLE AUTHENTICATION")
        print("="*80)
        print(">>> In the browser window:")
        print(">>>   1. Navigate to Settings > Users (using Buz menu)")
        print(">>>   2. Complete any additional authentication if prompted")
        print(">>>   3. Wait for the user table to load")
        print("="*80)

        # Wait for user confirmation
        input("\n>>> Press ENTER when you see the user table... ")

        print("\n>>> Verifying user table is visible...")
        try:
            await page.wait_for_selector('table#userListTable', state='visible', timeout=10000)
            print(f"✓ User table found!")
            print(f"  Current URL: {page.url}")
        except Exception as e:
            print(f"⚠️  WARNING: Could not find user table!")
            print(f"  Current URL: {page.url}")
            print(f"  Make sure you're on the Users page.")
            confirm = input("  Continue anyway? (y/n): ")
            if confirm.lower() != 'y':
                print("\nAborting. Please navigate to the Users page and try again.")
                await browser.close()
                return

        # Also visit console1 to capture cookies for that domain
        print("\n" + "="*80)
        print(">>> Step 4: CAPTURE CONSOLE1 DOMAIN COOKIES")
        print("="*80)
        print(">>> In the SAME browser tab (don't open a new tab):")
        print(">>>   Navigate to: https://console1.buzmanager.com/myorg/user-management/users")
        print(">>>   (You may need to authenticate again)")
        print(">>>")
        print(">>> The script will detect when you've navigated there")
        print("="*80)

        print("\n>>> Waiting for navigation to console1...")
        try:
            await page.wait_for_url(
                lambda url: "console1.buzmanager.com" in url,
                timeout=300_000  # 5 minutes
            )
            print("✓ Console1 page detected!")
            print(f"  Current URL: {page.url}")
        except Exception as e:
            print(f"\n⚠️  Timeout waiting for console1 navigation")
            print(f"  Current URL: {page.url}")
            print("  Make sure you navigated in the SAME tab (not a new tab)")
            confirm = input("  Continue anyway? (y/n): ")
            if confirm.lower() != 'y':
                print("\nAborting. Please navigate in the same tab and try again.")
                await browser.close()
                return

        # Save storage state (includes cookies for both domains)
        await ctx.storage_state(path=str(state_path))

        print("\n" + "="*80)
        print("✓ SUCCESS!")
        print("="*80)
        print(f"✓ Auth state saved to: {state_path.resolve()}")
        print(f"✓ Organization configured: {org_name}")
        print(f"✓ Cookies saved for:")
        print("    - go.buzmanager.com")
        print("    - console1.buzmanager.com")
        print("\n✓ Banji can now use this storage state to authenticate as this org")
        print("="*80 + "\n")

        await browser.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("ERROR: Organization name required!")
        print("\nUsage:")
        print("  python tools/buz_auth_bootstrap.py <org_name>")
        print("\nExample:")
        print("  python tools/buz_auth_bootstrap.py designer_drapes")
        print("  python tools/buz_auth_bootstrap.py canberra")
        print("  python tools/buz_auth_bootstrap.py tweed")
        sys.exit(1)

    org_name = sys.argv[1]
    print(f"\nStarting authentication bootstrap for organization: {org_name}\n")
    asyncio.run(main(org_name))
