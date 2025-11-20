#!/usr/bin/env python3
"""
Production Readiness Verification Script for Banji.

This script verifies that all dependencies are installed and Playwright can launch
in the production environment.

Run this on your production server before deploying Banji.
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import subprocess
import platform


def print_section(title):
    """Print a section header."""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)


def check_mark(success):
    """Return check or X mark."""
    return "✓" if success else "✗"


def check_python_version():
    """Check Python version is 3.8+."""
    print_section("Python Version Check")
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    success = version.major >= 3 and version.minor >= 8

    print(f"{check_mark(success)} Python version: {version_str}")

    if not success:
        print("\n❌ Python 3.8 or higher is required")
        print("   Current version:", version_str)
        return False

    print("✓ Python version is compatible")
    return True


def check_playwright_installed():
    """Check if playwright package is installed."""
    print_section("Playwright Package Check")

    try:
        import playwright
        version = playwright.__version__
        print(f"✓ Playwright package installed: {version}")
        return True
    except ImportError:
        print("✗ Playwright package not installed")
        print("\n❌ Install with: pip install playwright")
        return False


def check_playwright_browsers():
    """Check if Playwright browsers are installed."""
    print_section("Playwright Browser Check")

    try:
        result = subprocess.run(
            ['playwright', 'install', '--dry-run', 'chromium'],
            capture_output=True,
            text=True,
            timeout=10
        )

        # If dry-run completes without errors, browsers are likely installed
        # This is a heuristic - not perfect but good enough
        if result.returncode == 0:
            print("✓ Playwright browsers appear to be installed")
            return True
        else:
            print("✗ Playwright browsers may not be installed")
            print("\n❌ Install with: playwright install chromium")
            return False

    except FileNotFoundError:
        print("✗ playwright CLI not found")
        print("\n❌ Install with: playwright install chromium")
        return False
    except Exception as e:
        print(f"⚠️  Could not verify browser installation: {e}")
        print("   Attempting to launch browser to verify...")
        return None  # Will check with actual launch


def check_system_dependencies():
    """Check if system dependencies are installed (Linux only)."""
    print_section("System Dependencies Check (Linux)")

    system = platform.system()

    if system != "Linux":
        print(f"ℹ️  Running on {system} - skipping Linux dependency check")
        return True

    # List of critical libraries Playwright needs on Linux
    critical_libs = [
        'libnss3.so',
        'libatk-1.0.so',
        'libgbm.so',
        'libasound.so'
    ]

    missing = []

    for lib in critical_libs:
        # Try to find library using ldconfig
        try:
            result = subprocess.run(
                ['ldconfig', '-p'],
                capture_output=True,
                text=True,
                timeout=5
            )

            if lib not in result.stdout:
                missing.append(lib)

        except (FileNotFoundError, subprocess.TimeoutExpired):
            # Can't verify with ldconfig
            print("⚠️  Could not verify system dependencies (ldconfig not available)")
            print("   Will attempt browser launch test instead")
            return None

    if missing:
        print(f"✗ Missing system libraries: {', '.join(missing)}")
        print("\n❌ Install system dependencies with:")
        print("   playwright install-deps chromium")
        print("\n   Or on Ubuntu/Debian:")
        print("   sudo apt-get install libnss3 libatk-bridge2.0-0 libdrm2 libgbm1 libasound2")
        return False

    print("✓ Critical system libraries appear to be installed")
    return True


def check_browser_launch():
    """Actually try to launch a browser."""
    print_section("Browser Launch Test")

    print("Attempting to launch Chromium in headless mode...")

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Navigate to a simple page
            page.goto("data:text/html,<h1>Test</h1>")
            content = page.content()

            browser.close()

            if "Test" in content:
                print("✓ Browser launched successfully!")
                print("✓ Browser can navigate and render pages")
                return True
            else:
                print("✗ Browser launched but could not render page")
                return False

    except Exception as e:
        print(f"✗ Browser launch failed: {e}")
        print("\nCommon issues:")
        print("  1. Missing system dependencies (run: playwright install-deps chromium)")
        print("  2. Browser not installed (run: playwright install chromium)")
        print("  3. Permission issues with /tmp or ~/.cache directories")
        return False


def check_env_file():
    """Check if .env file exists with required variables."""
    print_section("Environment Configuration Check")

    env_path = Path(__file__).resolve().parents[1] / ".env"

    if not env_path.exists():
        print("⚠️  .env file not found")
        print(f"   Expected location: {env_path}")
        print("\n💡 Copy .env.example to .env and configure:")
        print("   cp banji/.env.example banji/.env")
        return False

    print(f"✓ .env file exists: {env_path}")

    # Check for required variables
    required_vars = ['BUZ_ORGS']
    missing_vars = []

    with open(env_path) as f:
        content = f.read()
        for var in required_vars:
            if f"{var}=" not in content or f"{var}=" == f"{var}=\n":
                missing_vars.append(var)

    if missing_vars:
        print(f"⚠️  Missing or empty variables: {', '.join(missing_vars)}")
        print("\n💡 Configure these in your .env file")
        return False

    print("✓ Required environment variables appear to be set")
    return True


def check_storage_state_files():
    """Check if storage state files exist for configured orgs."""
    print_section("Authentication Storage State Check")

    # Load .env to get orgs
    env_path = Path(__file__).resolve().parents[1] / ".env"

    if not env_path.exists():
        print("⚠️  .env file not found - skipping storage state check")
        return False

    # Simple .env parsing
    orgs = None
    with open(env_path) as f:
        for line in f:
            if line.startswith('BUZ_ORGS='):
                orgs = line.split('=', 1)[1].strip().strip('"\'')
                break

    if not orgs:
        print("⚠️  BUZ_ORGS not set in .env")
        return False

    org_names = [name.strip() for name in orgs.split(',') if name.strip()]

    secrets_dir = Path(__file__).resolve().parents[1] / ".secrets"
    missing_files = []

    for org_name in org_names:
        storage_file = secrets_dir / f"buz_storage_state_{org_name}.json"
        if storage_file.exists():
            print(f"✓ Storage state exists for: {org_name}")
        else:
            print(f"✗ Storage state missing for: {org_name}")
            missing_files.append(org_name)

    if missing_files:
        print(f"\n❌ Missing storage state files for: {', '.join(missing_files)}")
        print("\n💡 Generate with bootstrap tool:")
        for org in missing_files:
            print(f"   python tools/buz_auth_bootstrap.py {org}")
        return False

    print("\n✓ All storage state files present")
    return True


def main():
    """Run all checks."""
    print("\n" + "╔" + "="*58 + "╗")
    print("║  Banji Production Readiness Verification               ║")
    print("╚" + "="*58 + "╝")

    checks = [
        ("Python Version", check_python_version),
        ("Playwright Package", check_playwright_installed),
        ("Playwright Browsers", check_playwright_browsers),
        ("System Dependencies", check_system_dependencies),
        ("Browser Launch", check_browser_launch),
        ("Environment Config", check_env_file),
        ("Auth Storage States", check_storage_state_files),
    ]

    results = []

    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))

            # If a check returns None, it means uncertain - still continue
            if result is False:
                # Continue checking but note the failure
                pass

        except Exception as e:
            print(f"\n❌ Error during {name} check: {e}")
            results.append((name, False))

    # Summary
    print_section("Summary")

    passed = sum(1 for _, result in results if result is True)
    failed = sum(1 for _, result in results if result is False)
    uncertain = sum(1 for _, result in results if result is None)

    for name, result in results:
        if result is True:
            print(f"✓ {name}")
        elif result is False:
            print(f"✗ {name}")
        else:
            print(f"⚠️  {name} (uncertain)")

    print(f"\nPassed: {passed}/{len(results)}")

    if failed == 0 and uncertain == 0:
        print("\n" + "="*60)
        print("🎉 All checks passed! Banji is ready for production!")
        print("="*60)
        return 0
    elif failed > 0:
        print("\n" + "="*60)
        print("❌ Some checks failed. Fix the issues above before deploying.")
        print("="*60)
        return 1
    else:
        print("\n" + "="*60)
        print("⚠️  Some checks are uncertain. Review output above.")
        print("="*60)
        return 0


if __name__ == '__main__':
    sys.exit(main())
