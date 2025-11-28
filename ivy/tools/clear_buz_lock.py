#!/usr/bin/env python3
"""
Clear stale Buz Playwright lock files.

Usage: python ivy/tools/clear_buz_lock.py [--force]

Without --force, shows current lock status.
With --force, clears the lock files.
"""
import sys
from pathlib import Path

# Find the lock files
SECRETS_DIR = Path(__file__).parent.parent.parent / '.secrets'
LOCK_PATH = SECRETS_DIR / 'buz_playwright.lock'
INFO_PATH = SECRETS_DIR / 'buz_playwright.info'


def get_lock_status():
    """Get current lock status."""
    info = None
    if INFO_PATH.exists():
        try:
            import json
            info = json.loads(INFO_PATH.read_text())
        except Exception:
            info = {'error': 'Could not read info file'}

    return {
        'lock_exists': LOCK_PATH.exists(),
        'info_exists': INFO_PATH.exists(),
        'holder_info': info
    }


def clear_lock():
    """Clear the lock files."""
    cleared = []
    if LOCK_PATH.exists():
        LOCK_PATH.unlink()
        cleared.append(str(LOCK_PATH))
    if INFO_PATH.exists():
        INFO_PATH.unlink()
        cleared.append(str(INFO_PATH))
    return cleared


def main():
    force = '--force' in sys.argv

    status = get_lock_status()

    if not status['lock_exists'] and not status['info_exists']:
        print("No lock files found - lock is clear.")
        return

    print("Current lock status:")
    print(f"  Lock file: {'EXISTS' if status['lock_exists'] else 'not present'}")
    print(f"  Info file: {'EXISTS' if status['info_exists'] else 'not present'}")

    if status['holder_info']:
        info = status['holder_info']
        if 'error' in info:
            print(f"  Holder: {info['error']}")
        else:
            print(f"  Holder: {info.get('bot', 'unknown')}")
            print(f"  Acquired: {info.get('acquired_at', 'unknown')}")
            print(f"  PID: {info.get('pid', 'unknown')}")

    if not force:
        print("\nTo clear the lock, run with --force")
        return

    print("\nClearing lock files...")
    cleared = clear_lock()
    if cleared:
        for f in cleared:
            print(f"  Removed: {f}")
        print("Lock cleared.")
    else:
        print("No files to clear.")


if __name__ == '__main__':
    main()
