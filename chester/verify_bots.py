#!/usr/bin/env python3
"""
Verify that all bots from config.yaml are in Chester's database.
Run this on the production server to check sync status.

Usage:
    python3 verify_bots.py              # Just check status
    python3 verify_bots.py --sync       # Force sync if needed
"""
import sys
from pathlib import Path

# Add bot-team to path for imports
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from chester.services.database import db
from chester.config import config
from shared.config.ports import get_port


def verify_bots():
    """Check which bots are in config.yaml but not in database."""
    # Get all bots from database
    db_bots = {bot['name'] for bot in db.get_all_bots()}

    # Get all bots from config.yaml
    config_bots = set(config.bot_team.keys())

    # Find missing bots
    missing_bots = config_bots - db_bots

    print(f"📊 Bot Status Report")
    print(f"=" * 60)
    print(f"Bots in config.yaml:  {len(config_bots)}")
    print(f"Bots in database:     {len(db_bots)}")
    print(f"Missing from DB:      {len(missing_bots)}")
    print(f"=" * 60)

    if missing_bots:
        print(f"\n⚠️  Missing bots: {', '.join(sorted(missing_bots))}")
        print(f"\nThese bots are in config.yaml but not in Chester's database.")
        print(f"They will NOT appear in Dorothy until synced.\n")
        return False
    else:
        print(f"\n✅ All bots from config.yaml are in the database!")
        print(f"\nBot list: {', '.join(sorted(db_bots))}\n")
        return True


def sync_bots():
    """Manually trigger bot sync."""
    print(f"\n🔄 Syncing bots from config.yaml to database...")
    result = db.sync_bots_from_config(verbose=True)

    if result['added']:
        print(f"\n✅ Added {len(result['added'])} bot(s): {', '.join(result['added'])}")
    else:
        print(f"\n✅ No new bots to add (all in sync)")

    if result['skipped']:
        print(f"   Skipped {len(result['skipped'])} bot(s) (already exist or missing port)")

    print()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Verify Chester bot database sync')
    parser.add_argument('--sync', action='store_true',
                       help='Force sync bots from config.yaml')
    args = parser.parse_args()

    # Check current status
    all_synced = verify_bots()

    # Sync if requested
    if args.sync:
        sync_bots()
        print(f"Verifying after sync...")
        verify_bots()
    elif not all_synced:
        print(f"💡 Tip: Run with --sync to add missing bots to database")
        sys.exit(1)
